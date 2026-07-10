from datetime import timedelta

import app.services.knowledge_service as ks_module
from app.core.time import utc_now
from app.schemas.insights import (
    AutomationPlan,
    BottleneckPlan,
    ClusterGroup,
    ClusterPlan,
    ConsolidationGroup,
    ConsolidationPlan,
    DepartmentAnalysisPlan,
    ThemeDoc,
    TicketSignature,
)
from app.services.knowledge_service import KnowledgeService


class FakeOpenAI:
    def __init__(self) -> None:
        self.model = "test-model"
        self.summarize_calls = 0
        self._chunk = 0

    async def summarize_ticket_history(self, context):
        self.summarize_calls += 1
        subject = str(context.get("subject") or "")
        category = subject.split("-")[0] if "-" in subject else "general"
        return TicketSignature(problem=subject, category=category, tags=[category])

    async def cluster_ticket_signatures(self, signatures):
        # Tag titles per batch so the SAME category yields near-duplicate candidate
        # titles across chunks (e.g. "login b1", "login b2") — the fragmentation the
        # consolidation pass must collapse.
        self._chunk += 1
        by_cat: dict[str, list[str]] = {}
        for s in signatures:
            by_cat.setdefault(s["category"], []).append(s["key"])
        return ClusterPlan(
            clusters=[ClusterGroup(title=f"{cat} b{self._chunk}", ticket_keys=keys) for cat, keys in by_cat.items()]
        )

    async def consolidate_themes(self, context):
        # Canonical = first word of each candidate title; near-duplicates sharing
        # a first word merge into one canonical theme.
        groups: dict[str, list[str]] = {}
        for lab in context.get("labels", []):
            first = str(lab["title"]).split()[0].lower()
            groups.setdefault(first, []).append(str(lab["title"]))
        return ConsolidationPlan(
            groups=[ConsolidationGroup(canonical_title=canon, members=members) for canon, members in groups.items()]
        )

    async def write_theme_doc(self, context):
        return ThemeDoc(title=context["title"], summary="doc", symptoms="s", root_causes="rc", resolution_steps="steps")

    async def analyze_department(self, context):
        metrics = context.get("metrics") or []
        top = max(metrics, key=lambda m: m.get("volume", 0), default={"category": "general"})
        cat = top["category"]
        return DepartmentAnalysisPlan(
            bottlenecks=[BottleneckPlan(title="B", description="d", severity="high", category=cat)],
            automation=[AutomationPlan(title="A", description="d", rationale="r", category=cat)],
        )


class FakeArchiveRepo:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs

    async def find_needing_signature(self, statuses, limit=200):
        out = []
        for d in self.docs:
            stale = d.get("signature") is None or d.get("signature_source_updated_at") != d.get("updated_at_fresh")
            if d["status"] in statuses and stale:
                out.append(d)
            if len(out) >= limit:
                break
        return out

    async def set_signature(self, workspace_id, ticket_id, signature, source_updated_at):
        for d in self.docs:
            if d["workspace_id"] == workspace_id and d["ticket_id"] == ticket_id:
                d["signature"] = signature
                d["signature_source_updated_at"] = source_updated_at

    async def iter_for_scope(self, statuses):
        return [d for d in self.docs if d["status"] in statuses and d.get("signature") is not None]


class FakeKnowledgeRepo:
    def __init__(self) -> None:
        self.doc: dict | None = None

    async def get_current(self):
        return self.doc

    async def save_current(self, departments, model):
        self.doc = {"departments": departments, "model": model, "generated_at": utc_now()}


def _doc(workspace_id, ticket_id, subject, name, status="resolved", resolution_hours=None):
    created = utc_now() - timedelta(hours=resolution_hours) if resolution_hours is not None else None
    resolved = utc_now() if resolution_hours is not None else None
    return {
        "workspace_id": workspace_id,
        "workspace_name": name,
        "ticket_id": ticket_id,
        "subject": subject,
        "status": status,
        "priority": "low",
        "description": "",
        "conversations": [],
        "created_at_fresh": created,
        "resolved_at": resolved,
        "updated_at_fresh": utc_now(),
        "raw": {},
        "signature": None,
        "signature_source_updated_at": None,
    }


async def test_ensure_signatures_only_processes_unsigned():
    docs = [_doc("w1", "1", "login-a", "IT"), _doc("w1", "2", "login-b", "IT"), _doc("w1", "3", "billing-a", "IT")]
    docs[2]["signature"] = {"problem": "x", "category": "billing"}
    docs[2]["signature_source_updated_at"] = docs[2]["updated_at_fresh"]
    openai = FakeOpenAI()
    service = KnowledgeService(openai, FakeArchiveRepo(docs), FakeKnowledgeRepo())

    computed = await service.ensure_signatures(["resolved", "closed"])

    assert computed == 2
    assert openai.summarize_calls == 2


async def test_generate_groups_by_department():
    docs = [
        _doc("w1", "1", "login-a", "IT"),
        _doc("w1", "2", "login-b", "IT"),
        _doc("w2", "3", "envio-a", "Logística"),
    ]
    openai = FakeOpenAI()
    service = KnowledgeService(openai, FakeArchiveRepo(docs), FakeKnowledgeRepo())

    response = await service.generate(["resolved", "closed"])

    depts = {d.name: d for d in response.departments}
    assert set(depts) == {"IT", "Logística"}
    assert depts["IT"].total_tickets == 2
    assert depts["Logística"].total_tickets == 1
    # each department carries the four dimensions
    it = depts["IT"]
    assert it.themes and it.recurring and it.metrics and it.bottlenecks and it.automation
    assert response.persisted is True


async def test_generate_filters_by_status():
    docs = [_doc("w1", "1", "login-a", "IT"), _doc("w1", "2", "login-b", "IT", status="open")]
    openai = FakeOpenAI()
    service = KnowledgeService(openai, FakeArchiveRepo(docs), FakeKnowledgeRepo())

    response = await service.generate(["resolved", "closed"])

    refs = [r.ticket_id for d in response.departments for t in d.themes for r in t.ticket_refs]
    assert refs == ["1"]


async def test_metrics_compute_volume_and_resolution():
    docs = [
        _doc("w1", "1", "login-a", "IT", resolution_hours=2),
        _doc("w1", "2", "login-b", "IT", resolution_hours=4),
    ]
    openai = FakeOpenAI()
    service = KnowledgeService(openai, FakeArchiveRepo(docs), FakeKnowledgeRepo())

    response = await service.generate(["resolved", "closed"])

    metric = response.departments[0].metrics[0]
    assert metric.category == "login"
    assert metric.volume == 2
    assert metric.avg_resolution_hours == 3.0  # (2 + 4) / 2


async def test_bottlenecks_attach_ticket_refs_by_category():
    docs = [_doc("w1", "1", "login-a", "IT"), _doc("w1", "2", "login-b", "IT")]
    openai = FakeOpenAI()
    service = KnowledgeService(openai, FakeArchiveRepo(docs), FakeKnowledgeRepo())

    response = await service.generate(["resolved", "closed"])

    bottleneck = response.departments[0].bottlenecks[0]
    assert bottleneck.category == "login"
    assert {r.ticket_id for r in bottleneck.ticket_refs} == {"1", "2"}


async def test_consolidation_merges_fragmented_themes_across_chunks(monkeypatch):
    # Chunk size 1 forces each ticket into its own clustering batch, producing
    # fragmented candidate titles ("login b1", "login b2", ...) that the
    # consolidation pass must collapse into a single canonical theme.
    monkeypatch.setattr(ks_module, "CLUSTER_CHUNK", 1)
    docs = [
        _doc("w1", "1", "login-a", "IT"),
        _doc("w1", "2", "login-b", "IT"),
        _doc("w1", "3", "login-c", "IT"),
    ]
    openai = FakeOpenAI()
    service = KnowledgeService(openai, FakeArchiveRepo(docs), FakeKnowledgeRepo())

    response = await service.generate(["resolved", "closed"])

    it = response.departments[0]
    # 3 fragmented candidates → 1 canonical theme covering all 3 tickets
    assert len(it.themes) == 1
    assert it.themes[0].title == "login"
    assert it.themes[0].frequency == 3
    assert {r.ticket_id for r in it.themes[0].ticket_refs} == {"1", "2", "3"}
    # metrics are per canonical theme, not per fragmented candidate
    assert len(it.metrics) == 1
    assert it.metrics[0].category == "login"
    assert it.metrics[0].volume == 3


async def test_generate_empty_persists_empty_base():
    openai = FakeOpenAI()
    service = KnowledgeService(openai, FakeArchiveRepo([]), FakeKnowledgeRepo())

    response = await service.generate(["resolved", "closed"])

    assert response.departments == []
    assert response.persisted is True
