from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import Settings
from app.core.time import utc_now
from app.integrations.fresh_archive import PER_PAGE, FreshArchiveClient
from app.integrations.rate_limiter import AsyncRateLimiter
from app.repositories.fresh_harvest_state_repository import FreshHarvestStateRepository
from app.repositories.fresh_ticket_archive_repository import FreshTicketArchiveRepository
from app.schemas.insights import HarvestStatus, WorkspaceHarvestStatus, WorkspaceOption, WorkspacesResponse
from app.schemas.settings import FreshWorkspaceConfig
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)

# Freshservice paginates the list endpoint up to ~100 pages; when we hit this
# ceiling we advance the updated_since cursor and reset to page 1.
PAGE_CAP = 100
# Bound concurrent conversation fetches (the shared rate limiter paces requests).
CONVO_CONCURRENCY = 5


class FreshArchiveService:
    """Harvest Freshservice ticket history into the archive, resumably.

    Parameters:
        settings: Global settings (Freshservice creds + rate limit + window).
        settings_service: Source of the configured workspaces (AppSettings).
        archive_repo: Ticket archive persistence.
        harvest_state_repo: Per-workspace resumable cursor persistence.

    Returns:
        Service producing and maintaining the ticket archive.

    Edge cases:
        With no configured workspaces it falls back to a single workspace built
        from the global fresh_workspace_id. Upserts are idempotent, so a resumed
        backfill safely re-fetches the last checkpointed page.
    """

    def __init__(
        self,
        settings: Settings,
        settings_service: SettingsService,
        archive_repo: FreshTicketArchiveRepository,
        harvest_state_repo: FreshHarvestStateRepository,
    ) -> None:
        self._settings = settings
        self._settings_service = settings_service
        self._archive_repo = archive_repo
        self._state_repo = harvest_state_repo

    async def _workspaces(self) -> list[FreshWorkspaceConfig]:
        """Return configured workspaces, resolving credential fallbacks.

        Edge cases:
            Empty config falls back to one workspace synthesized from the global
            fresh_workspace_id (or "default" when even that is empty).
        """
        app_settings = await self._settings_service.get_settings()
        configs = list(app_settings.fresh_workspaces)
        if not configs:
            configs = [
                FreshWorkspaceConfig(
                    workspace_id=self._settings.fresh_workspace_id or "default",
                    name="Freshservice",
                )
            ]
        resolved: list[FreshWorkspaceConfig] = []
        for cfg in configs:
            resolved.append(
                FreshWorkspaceConfig(
                    workspace_id=cfg.workspace_id,
                    name=cfg.name or cfg.workspace_id,
                    base_url=cfg.base_url or self._settings.fresh_base_url,
                    api_key=cfg.api_key or self._settings.fresh_api_key,
                )
            )
        return resolved

    def _client_for(self, ws: FreshWorkspaceConfig, limiter: AsyncRateLimiter, sem: asyncio.Semaphore) -> FreshArchiveClient:
        """Build a harvest client for a resolved workspace config."""
        return FreshArchiveClient(ws.base_url, ws.api_key, ws.workspace_id, limiter, sem)

    def _since(self, months: int) -> datetime:
        """Compute the earliest updated_since bound from a month window."""
        return utc_now() - timedelta(days=30 * max(months, 1))

    async def _tuning(self) -> tuple[int, int]:
        """Return (rate_per_min, since_months) from the editable app settings.

        These live on AppSettings (DB-editable), not the env-first core Settings,
        so they are read via the settings service.
        """
        app_settings = await self._settings_service.get_settings()
        return app_settings.fresh_rate_limit_per_min, app_settings.fresh_archive_since_months

    async def backfill(self, workspace_id: str | None = None, since_months: int | None = None) -> HarvestStatus:
        """Run a resumable historic backfill across workspaces.

        Parameters:
            workspace_id: Limit to a single workspace when provided.
            since_months: Override the configured history window.

        Returns:
            Aggregate harvest status after the run.

        Edge cases:
            Resumes from the persisted window cursor; re-fetches the last page
            (idempotent). Marks backfill_done when a workspace is exhausted.
        """
        rate_per_min, default_months = await self._tuning()
        limiter = AsyncRateLimiter(rate_per_min)
        sem = asyncio.Semaphore(CONVO_CONCURRENCY)
        since = self._since(since_months if since_months is not None else default_months)

        for ws in await self._workspaces():
            if workspace_id and ws.workspace_id != workspace_id:
                continue
            state = await self._state_repo.get(ws.workspace_id) or {}
            # Resume an interrupted run from its checkpoint; otherwise start from the
            # requested window (`since`). backfill_since is display metadata only —
            # using it as the cursor would make a completed window "sticky" and
            # silently ignore a newly-requested larger window.
            cursor = _parse_dt(state.get("backfill_window_cursor")) or since
            await self._state_repo.upsert(ws.workspace_id, {"in_progress": True, "backfill_since": since})
            client = self._client_for(ws, limiter, sem)
            try:
                last_updated = await self._harvest(
                    client, ws.workspace_id, ws.name, cursor, checkpoint_field="backfill_window_cursor"
                )
                await self._state_repo.upsert(
                    ws.workspace_id,
                    {
                        "in_progress": False,
                        "backfill_done": True,
                        "backfill_window_cursor": None,
                        "last_incremental_at": (last_updated or utc_now()),
                        "last_error": None,
                    },
                )
            except Exception as exc:  # noqa: BLE001 — one workspace must not abort the others
                note = _error_note(exc)
                await self._state_repo.upsert(ws.workspace_id, {"in_progress": False, "last_error": note})
                logger.warning("Backfill skipped workspace %s: %s", ws.workspace_id, note)
        return await self.status()

    async def sync_incremental(self) -> HarvestStatus:
        """Fetch tickets updated since each workspace's last sync and upsert them.

        Returns:
            Aggregate harvest status after the run.

        Edge cases:
            First run (no cursor) falls back to the configured history window.
        """
        rate_per_min, default_months = await self._tuning()
        limiter = AsyncRateLimiter(rate_per_min)
        sem = asyncio.Semaphore(CONVO_CONCURRENCY)
        for ws in await self._workspaces():
            state = await self._state_repo.get(ws.workspace_id) or {}
            cursor = _parse_dt(state.get("last_incremental_at")) or self._since(default_months)
            await self._state_repo.upsert(ws.workspace_id, {"in_progress": True})
            client = self._client_for(ws, limiter, sem)
            try:
                last_updated = await self._harvest(client, ws.workspace_id, ws.name, cursor, checkpoint_field=None)
                await self._state_repo.upsert(
                    ws.workspace_id,
                    {"in_progress": False, "last_incremental_at": (last_updated or utc_now()), "last_error": None},
                )
            except Exception as exc:  # noqa: BLE001 — one workspace must not abort the others
                note = _error_note(exc)
                await self._state_repo.upsert(ws.workspace_id, {"in_progress": False, "last_error": note})
                logger.warning("Incremental sync skipped workspace %s: %s", ws.workspace_id, note)
        return await self.status()

    async def _harvest(
        self,
        client: FreshArchiveClient,
        workspace_id: str,
        workspace_name: str,
        cursor: datetime,
        checkpoint_field: str | None,
    ) -> datetime | None:
        """Page through tickets from a cursor, upserting each page with conversations.

        Parameters:
            client: Harvest client for the workspace.
            workspace_id: Workspace being harvested.
            cursor: Earliest updated_since bound to start from.
            checkpoint_field: State field to persist the advancing cursor into
                (for resumable backfill), or None for incremental runs.

        Returns:
            The most recent updated_at seen, or None when nothing was fetched.

        Edge cases:
            Advances the cursor and resets to page 1 when Freshservice's page
            ceiling is reached, so history beyond ~9000 tickets is still walked.
        """
        page = 1
        fetched = upserted = convos = 0
        max_updated: datetime | None = None
        while True:
            docs = await client.fetch_tickets_page(cursor, page)
            if not docs:
                break
            for doc in docs:
                doc["workspace_name"] = workspace_name
            docs = await self._attach_conversations(client, docs)
            convos += sum(len(d.get("conversations") or []) for d in docs)
            upserted += await self._archive_repo.bulk_upsert(docs)
            fetched += len(docs)

            page_max = _max_updated(docs)
            if page_max and (max_updated is None or page_max > max_updated):
                max_updated = page_max

            await self._state_repo.upsert(
                workspace_id,
                {
                    "stats": {"fetched": fetched, "upserted": upserted, "convos": convos},
                    **({checkpoint_field: cursor} if checkpoint_field else {}),
                },
            )

            if len(docs) < PER_PAGE:
                break
            if page >= PAGE_CAP:
                # Advance the window past the last-seen update to beat the page ceiling.
                if page_max and page_max > cursor:
                    cursor = page_max
                    page = 1
                else:
                    break
            else:
                page += 1
        return max_updated

    async def _attach_conversations(self, client: FreshArchiveClient, docs: list[dict]) -> list[dict]:
        """Fetch and attach conversations for each doc, bounded and fault-tolerant."""

        async def one(doc: dict) -> dict:
            try:
                doc["conversations"] = await client.fetch_conversations(doc["ticket_id"])
            except Exception:  # noqa: BLE001 — a single ticket's convos must not abort the harvest
                logger.warning("Conversations fetch failed for ticket %s", doc.get("ticket_id"))
                doc["conversations"] = []
            return doc

        return await asyncio.gather(*[one(doc) for doc in docs])

    async def discover_workspaces(self) -> list[WorkspaceOption]:
        """List workspaces available in the Freshservice instance.

        Returns:
            Workspace options (id + name) from GET /api/v2/workspaces.

        Edge cases:
            Without global credentials returns a single mock workspace so the
            discovery UI still renders locally.
        """
        base = self._settings.fresh_base_url.strip().rstrip("/")
        api_key = self._settings.fresh_api_key.strip()
        if not (base and api_key):
            return [WorkspaceOption(workspace_id="default", name="Freshservice (mock)")]
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{base}/api/v2/workspaces", auth=(api_key, "X"))
            response.raise_for_status()
            payload = response.json()
        items = payload.get("workspaces", payload) if isinstance(payload, dict) else payload
        options: list[WorkspaceOption] = []
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict) and item.get("id") is not None:
                options.append(WorkspaceOption(workspace_id=str(item["id"]), name=str(item.get("name") or item["id"])))
        return options

    async def workspaces_overview(self) -> WorkspacesResponse:
        """Return both available (API) and currently configured workspaces."""
        app_settings = await self._settings_service.get_settings()
        configured = [WorkspaceOption(workspace_id=w.workspace_id, name=w.name) for w in app_settings.fresh_workspaces]
        available: list[WorkspaceOption] = []
        try:
            available = await self.discover_workspaces()
        except httpx.HTTPError:
            logger.warning("Workspace discovery failed; returning configured only")
        return WorkspacesResponse(available=available, configured=configured)

    async def import_workspaces(self) -> WorkspacesResponse:
        """Discover workspaces and persist them into the app settings.

        Returns:
            The available + resulting configured workspaces.

        Edge cases:
            Existing per-workspace base_url/api_key overrides are preserved;
            configured workspaces not returned by the API are kept as-is.
        """
        available = await self.discover_workspaces()
        app_settings = await self._settings_service.get_settings()
        existing = {w.workspace_id: w for w in app_settings.fresh_workspaces}

        merged: list[FreshWorkspaceConfig] = []
        available_ids = {o.workspace_id for o in available}
        for option in available:
            prev = existing.get(option.workspace_id)
            merged.append(
                FreshWorkspaceConfig(
                    workspace_id=option.workspace_id,
                    name=option.name,
                    base_url=prev.base_url if prev else "",
                    api_key=prev.api_key if prev else "",
                )
            )
        # Preserve any manually-added workspace the API did not return.
        for wid, cfg in existing.items():
            if wid not in available_ids:
                merged.append(cfg)

        app_settings.fresh_workspaces = merged
        await self._settings_service.update_settings(app_settings)
        return WorkspacesResponse(
            available=available,
            configured=[WorkspaceOption(workspace_id=w.workspace_id, name=w.name) for w in merged],
        )

    async def status(self) -> HarvestStatus:
        """Aggregate per-workspace harvest state for the UI."""
        workspaces = await self._workspaces()
        states = {s["workspace_id"]: s for s in await self._state_repo.all()}
        rows: list[WorkspaceHarvestStatus] = []
        for ws in workspaces:
            st = states.get(ws.workspace_id, {})
            stats = st.get("stats") or {}
            rows.append(
                WorkspaceHarvestStatus(
                    workspace_id=ws.workspace_id,
                    name=ws.name,
                    backfill_done=bool(st.get("backfill_done")),
                    backfill_since=_parse_dt(st.get("backfill_since")),
                    last_incremental_at=_parse_dt(st.get("last_incremental_at")),
                    in_progress=bool(st.get("in_progress")),
                    fetched=int(stats.get("fetched", 0)),
                    upserted=int(stats.get("upserted", 0)),
                    convos=int(stats.get("convos", 0)),
                    archived_count=await self._archive_repo.count_for_workspace(ws.workspace_id),
                    last_error=st.get("last_error"),
                )
            )
        return HarvestStatus(workspaces=rows, total_archived=await self._archive_repo.count())


def _error_note(exc: Exception) -> str:
    """Human-readable note for a per-workspace harvest failure.

    Edge cases:
        401/403 → "sin permisos" so the UI can explain a workspace was skipped
        because the API key lacks access to it.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return f"sin permisos (HTTP {code})"
        return f"HTTP {code}"
    return str(exc)[:200] or exc.__class__.__name__


def _parse_dt(value: Any) -> datetime | None:
    """Coerce a stored value into a timezone-aware datetime, or None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _max_updated(docs: list[dict]) -> datetime | None:
    """Return the max updated_at_fresh across docs, or None."""
    values = [_parse_dt(d.get("updated_at_fresh")) for d in docs]
    values = [v for v in values if v is not None]
    return max(values) if values else None
