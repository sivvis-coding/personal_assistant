from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.core.time import utc_now
from app.integrations.openai_client import OpenAIClient
from app.repositories.fresh_knowledge_repository import FreshKnowledgeRepository
from app.repositories.fresh_ticket_archive_repository import FreshTicketArchiveRepository
from app.schemas.insights import (
    AutomationOpportunity,
    Bottleneck,
    CategoryMetric,
    ConsolidationGroup,
    DepartmentAnalysisPlan,
    DepartmentKnowledge,
    KnowledgeResponse,
    KnowledgeTheme,
    RecurringIssue,
    ThemeDoc,
    TicketRef,
    TicketSignature,
)

logger = logging.getLogger(__name__)

# Tickets summarized per map batch, and signatures per clustering call.
SIGNATURE_BATCH = 50
CLUSTER_CHUNK = 40
# Target size of the consolidated canonical theme taxonomy per department.
TARGET_THEMES_MIN = 15
TARGET_THEMES_MAX = 25
UNCLASSIFIED = "Sin clasificar"
# Safety cap so the map phase can never loop forever.
MAX_SIGNATURE_BATCHES = 1000
# How many conversation bodies (and chars each) to feed the signature prompt.
MAX_CONVOS = 20
MAX_CONVO_CHARS = 1500
# How many recurring-issue buckets to surface per department.
TOP_RECURRING = 20
# Max ticket references stored per bucket/theme (keeps docs and payloads small).
MAX_REFS = 25

# Default scope maximizes analysis coverage (bottlenecks need open/pending too).
ALL_STATUSES = [
    "open",
    "pending",
    "resolved",
    "closed",
    "waiting on customer",
    "waiting on third party",
]


class KnowledgeService:
    """Turn the ticket archive into per-department structured analysis.

    Parameters:
        openai_client: LLM client (signatures, clustering, theme docs, analysis).
        archive_repo: Ticket archive (source + signature cache).
        knowledge_repo: Persistence for the generated knowledge base.

    Returns:
        Service implementing the map (per-ticket signature) / reduce
        (per-department themes + metrics + bottlenecks + automation) pipeline.

    Edge cases:
        Signatures are cached on the archive; only new/changed tickets are
        re-summarized. Analysis is grouped by workspace = department.
    """

    def __init__(
        self,
        openai_client: OpenAIClient,
        archive_repo: FreshTicketArchiveRepository,
        knowledge_repo: FreshKnowledgeRepository,
    ) -> None:
        self._openai_client = openai_client
        self._archive_repo = archive_repo
        self._knowledge_repo = knowledge_repo

    async def ensure_signatures(self, statuses: list[str]) -> int:
        """Summarize every in-scope ticket lacking a fresh signature (cached map)."""
        computed = 0
        for _ in range(MAX_SIGNATURE_BATCHES):
            docs = await self._archive_repo.find_needing_signature(statuses, limit=SIGNATURE_BATCH)
            if not docs:
                break
            for doc in docs:
                try:
                    signature = await self._openai_client.summarize_ticket_history(_signature_context(doc))
                    sig_dict = signature.model_dump()
                except Exception:  # noqa: BLE001 — one bad ticket must not abort the whole map
                    logger.warning("Signature failed for %s:%s — using fallback", doc["workspace_id"], doc["ticket_id"])
                    sig_dict = TicketSignature(
                        problem=doc.get("subject") or "", category="sin clasificar"
                    ).model_dump()
                # Always persist (even the fallback) so the ticket is not retried forever.
                await self._archive_repo.set_signature(
                    doc["workspace_id"], doc["ticket_id"], sig_dict, doc.get("updated_at_fresh")
                )
                computed += 1
        return computed

    async def generate(self, statuses: list[str] | None = None) -> KnowledgeResponse:
        """Build and persist the per-department knowledge base.

        Parameters:
            statuses: Ticket statuses to include (defaults to all statuses so
                bottlenecks over open/pending tickets are captured).

        Returns:
            The freshly generated, persisted knowledge base split by department.

        Edge cases:
            With no signed tickets it persists and returns an empty base.
        """
        scope = statuses or ALL_STATUSES
        await self.ensure_signatures(scope)
        docs = await self._archive_repo.iter_for_scope(scope)
        if not docs:
            await self._knowledge_repo.save_current([], self._openai_client.model)
            return await self.get_persisted()

        by_workspace: dict[str, list[dict]] = {}
        for doc in docs:
            by_workspace.setdefault(doc["workspace_id"], []).append(doc)

        departments: list[DepartmentKnowledge] = []
        for workspace_id, ws_docs in by_workspace.items():
            try:
                departments.append(await self._department(workspace_id, ws_docs))
            except Exception:  # noqa: BLE001 — one department must not abort the others
                logger.exception("Department analysis failed for workspace %s", workspace_id)
        departments.sort(key=lambda d: d.total_tickets, reverse=True)

        await self._knowledge_repo.save_current([d.model_dump() for d in departments], self._openai_client.model)
        return await self.get_persisted()

    async def _department(self, workspace_id: str, docs: list[dict]) -> DepartmentKnowledge:
        """Build the full analysis for a single department (workspace)."""
        name = next((d.get("workspace_name") for d in docs if d.get("workspace_name")), workspace_id)
        doc_by_key = {_key(d): d for d in docs}

        # Two-level reduce: batch clustering → consolidation into a canonical taxonomy.
        candidates = await self._candidate_clusters(doc_by_key)
        themes, key_to_theme = await self._build_canonical_themes(candidates, doc_by_key)

        metrics = _metrics(docs, key_to_theme)
        recurring = [
            RecurringIssue(label=t.title, count=t.frequency, ticket_refs=t.ticket_refs[:MAX_REFS])
            for t in themes[:TOP_RECURRING]
        ]
        refs_by_theme = _refs_by_theme(docs, key_to_theme)

        try:
            analysis = await self._openai_client.analyze_department(
                {
                    "department": name,
                    "themes": [{"title": t.title, "frequency": t.frequency, "summary": t.summary} for t in themes],
                    "metrics": [m.model_dump() for m in metrics],
                }
            )
        except Exception:  # noqa: BLE001 — degrade to no bottlenecks/automation rather than lose the department
            logger.warning("Department analysis (bottlenecks/automation) failed for %s", name)
            analysis = DepartmentAnalysisPlan()
        bottlenecks = [
            Bottleneck(
                title=b.title,
                description=b.description,
                severity=b.severity,
                category=b.category,
                ticket_refs=refs_by_theme.get(b.category.strip().lower(), []),
            )
            for b in analysis.bottlenecks
        ]
        automation = [
            AutomationOpportunity(
                title=a.title,
                description=a.description,
                rationale=a.rationale,
                category=a.category,
                ticket_refs=refs_by_theme.get(a.category.strip().lower(), []),
            )
            for a in analysis.automation
        ]
        return DepartmentKnowledge(
            workspace_id=workspace_id,
            name=name,
            total_tickets=len(docs),
            themes=themes,
            recurring=recurring,
            bottlenecks=bottlenecks,
            automation=automation,
            metrics=metrics,
        )

    async def _candidate_clusters(self, doc_by_key: dict[str, dict]) -> dict[str, dict[str, Any]]:
        """Level 1: cluster signatures in batches into candidate themes.

        Returns:
            {norm_title: {title, keys}} — the raw, fragmented candidates (many
            near-duplicate titles across batches; consolidated in level 2).
        """
        signatures = [_cluster_input(d) for d in doc_by_key.values()]
        candidates: dict[str, dict[str, Any]] = {}
        for start in range(0, len(signatures), CLUSTER_CHUNK):
            chunk = signatures[start : start + CLUSTER_CHUNK]
            try:
                plan = await self._openai_client.cluster_ticket_signatures(chunk)
            except Exception:  # noqa: BLE001 — skip a failed chunk rather than lose the department
                logger.warning("Clustering failed for a chunk; skipping %d signatures", len(chunk))
                continue
            for cluster in plan.clusters:
                norm = cluster.title.strip().lower()
                bucket = candidates.setdefault(norm, {"title": cluster.title.strip(), "keys": []})
                bucket["keys"].extend(k for k in cluster.ticket_keys if k in doc_by_key)
        return candidates

    async def _build_canonical_themes(
        self, candidates: dict[str, dict[str, Any]], doc_by_key: dict[str, dict]
    ) -> tuple[list[KnowledgeTheme], dict[str, str]]:
        """Level 2: consolidate candidate titles into a canonical taxonomy and build docs.

        Returns:
            (themes, key_to_theme) where each ticket key maps to exactly one
            canonical theme title.

        Edge cases:
            If the consolidation LLM call fails, falls back to using the raw
            candidates as themes (previous behavior). Every ticket is assigned to
            exactly one theme; anything unmapped lands in "Sin clasificar".
        """
        if not candidates:
            return [], {}

        labels = [{"title": c["title"], "count": len(_dedupe(c["keys"]))} for c in candidates.values()]
        try:
            plan = await self._openai_client.consolidate_themes(
                {"labels": labels, "target_min": TARGET_THEMES_MIN, "target_max": TARGET_THEMES_MAX}
            )
            groups = plan.groups
        except Exception:  # noqa: BLE001 — degrade to un-consolidated candidates rather than lose the department
            logger.warning("Theme consolidation failed; falling back to raw candidates")
            groups = [ConsolidationGroup(canonical_title=c["title"], members=[c["title"]]) for c in candidates.values()]

        # Map each candidate (by normalized title) to its canonical theme.
        canonical_of_norm: dict[str, str] = {}
        for group in groups:
            canon = group.canonical_title.strip() or UNCLASSIFIED
            for member in group.members:
                mnorm = member.strip().lower()
                if mnorm in candidates and mnorm not in canonical_of_norm:
                    canonical_of_norm[mnorm] = canon
        for norm, cand in candidates.items():  # unmapped candidate → keeps its own title
            canonical_of_norm.setdefault(norm, cand["title"])

        # Union candidate keys into canonical themes; assign each ticket once
        # (largest candidates first so dominant themes seed the assignment).
        assigned: set[str] = set()
        canon_keys: dict[str, list[str]] = {}
        for norm, cand in sorted(candidates.items(), key=lambda kv: -len(kv[1]["keys"])):
            canon = canonical_of_norm[norm]
            bucket = canon_keys.setdefault(canon, [])
            for k in cand["keys"]:
                if k not in assigned:
                    assigned.add(k)
                    bucket.append(k)

        key_to_theme: dict[str, str] = {}
        themes: list[KnowledgeTheme] = []
        for canon, keys in canon_keys.items():
            keys = _dedupe(keys)
            if not keys:
                continue
            for k in keys:
                key_to_theme[k] = canon
            cluster_docs = [doc_by_key[k] for k in keys]
            try:
                theme_doc = await self._openai_client.write_theme_doc(
                    {"title": canon, "signatures": [_theme_signature(d) for d in cluster_docs]}
                )
            except Exception:  # noqa: BLE001 — keep the theme with a minimal doc rather than drop it
                logger.warning("Theme doc failed for '%s'; using minimal doc", canon)
                theme_doc = ThemeDoc(title=canon, summary="")
            themes.append(
                KnowledgeTheme(
                    title=canon,  # canonical title is authoritative for a stable taxonomy
                    summary=theme_doc.summary,
                    symptoms=theme_doc.symptoms,
                    root_causes=theme_doc.root_causes,
                    resolution_steps=theme_doc.resolution_steps,
                    frequency=len(keys),
                    workspaces=sorted({d["workspace_id"] for d in cluster_docs}),
                    ticket_refs=[_ref(d) for d in cluster_docs[:MAX_REFS]],
                )
            )
        themes.sort(key=lambda t: t.frequency, reverse=True)
        return themes, key_to_theme

    async def get_persisted(self) -> KnowledgeResponse:
        """Return the persisted knowledge base, or an empty un-persisted response."""
        doc = await self._knowledge_repo.get_current()
        if doc is None:
            return KnowledgeResponse(model=self._openai_client.model, generated_at=utc_now(), persisted=False)
        return KnowledgeResponse(
            departments=[DepartmentKnowledge.model_validate(d) for d in doc.get("departments", [])],
            model=doc.get("model", self._openai_client.model),
            generated_at=doc.get("generated_at", utc_now()),
            persisted=True,
        )


# --- helpers -----------------------------------------------------------------


def _key(doc: dict) -> str:
    return f'{doc["workspace_id"]}:{doc["ticket_id"]}'


def _dedupe(keys: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _signature_context(doc: dict) -> dict:
    convos = []
    for c in (doc.get("conversations") or [])[:MAX_CONVOS]:
        body = (c.get("body_text") or "")[:MAX_CONVO_CHARS]
        if body:
            convos.append({"kind": c.get("kind"), "body_text": body})
    return {
        "ticket_id": doc.get("ticket_id"),
        "subject": doc.get("subject"),
        "description": (doc.get("description") or "")[:MAX_CONVO_CHARS],
        "status": doc.get("status"),
        "priority": doc.get("priority"),
        "conversations": convos,
    }


def _cluster_input(doc: dict) -> dict:
    sig = doc.get("signature") or {}
    return {
        "key": _key(doc),
        "problem": sig.get("problem", ""),
        "category": sig.get("category", ""),
        "product_area": sig.get("product_area", ""),
        "tags": sig.get("tags", []),
    }


def _theme_signature(doc: dict) -> dict:
    sig = doc.get("signature") or {}
    return {
        "problem": sig.get("problem", ""),
        "root_cause": sig.get("root_cause", ""),
        "resolution": sig.get("resolution", ""),
        "product_area": sig.get("product_area", ""),
    }


def _ref(doc: dict) -> TicketRef:
    return TicketRef(workspace_id=doc["workspace_id"], ticket_id=doc["ticket_id"], subject=doc.get("subject", ""))


def _theme_of(doc: dict, key_to_theme: dict[str, str]) -> str:
    """Return the canonical theme a ticket belongs to, or the unclassified bucket."""
    return key_to_theme.get(_key(doc), UNCLASSIFIED)


def _refs_by_theme(docs: list[dict], key_to_theme: dict[str, str]) -> dict[str, list[TicketRef]]:
    """Map normalized canonical-theme title → sample ticket references."""
    out: dict[str, list[TicketRef]] = {}
    for doc in docs:
        label = _theme_of(doc, key_to_theme).strip().lower()
        out.setdefault(label, [])
        if len(out[label]) < MAX_REFS:
            out[label].append(_ref(doc))
    return out


def _metrics(docs: list[dict], key_to_theme: dict[str, str]) -> list[CategoryMetric]:
    """Compute structured metrics per canonical theme (volume, avg resolution, reopen)."""
    volume: Counter[str] = Counter()
    resolution_hours: dict[str, list[float]] = {}
    reopened: Counter[str] = Counter()
    for doc in docs:
        label = _theme_of(doc, key_to_theme)
        volume[label] += 1
        hours = _resolution_hours(doc)
        if hours is not None:
            resolution_hours.setdefault(label, []).append(hours)
        if _was_reopened(doc):
            reopened[label] += 1

    metrics: list[CategoryMetric] = []
    for label, count in volume.most_common():
        hrs = resolution_hours.get(label, [])
        avg = round(sum(hrs) / len(hrs), 1) if hrs else None
        rate = round(reopened[label] / count, 2) if count else None
        metrics.append(CategoryMetric(category=label, volume=count, avg_resolution_hours=avg, reopen_rate=rate))
    return metrics


def _resolution_hours(doc: dict) -> float | None:
    """Return resolution time in hours from created/resolved timestamps, or None."""
    created = _parse_dt(doc.get("created_at_fresh"))
    resolved = _parse_dt(doc.get("resolved_at"))
    if created and resolved and resolved >= created:
        return (resolved - created).total_seconds() / 3600.0
    return None


def _was_reopened(doc: dict) -> bool:
    """Best-effort reopen detection from Freshservice stats in the raw payload."""
    stats = (doc.get("raw") or {}).get("stats") or {}
    return bool(stats.get("reopened_at"))


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
