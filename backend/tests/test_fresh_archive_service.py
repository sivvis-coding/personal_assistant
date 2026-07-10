from datetime import timedelta

import httpx

import app.services.fresh_archive_service as svc_module
from app.core.config import Settings
from app.core.time import utc_now
from app.schemas.settings import AppSettings, FreshWorkspaceConfig
from app.services.fresh_archive_service import FreshArchiveService


class FakeArchiveClient:
    def __init__(self, pages: list[list[dict]], raise_status: int | None = None) -> None:
        self.pages = list(pages)
        self.calls: list[tuple] = []
        self._raise_status = raise_status

    async def fetch_tickets_page(self, updated_since, page):
        self.calls.append((updated_since, page))
        if self._raise_status is not None:
            request = httpx.Request("GET", "http://fs/api/v2/tickets")
            response = httpx.Response(self._raise_status, request=request)
            raise httpx.HTTPStatusError("forbidden", request=request, response=response)
        return self.pages.pop(0) if self.pages else []

    async def fetch_conversations(self, ticket_id):
        return []


class FakeArchiveRepo:
    def __init__(self) -> None:
        self.docs: dict[tuple, dict] = {}

    async def bulk_upsert(self, docs):
        for d in docs:
            self.docs[(d["workspace_id"], d["ticket_id"])] = d
        return len(docs)

    async def count(self):
        return len(self.docs)

    async def count_for_workspace(self, workspace_id):
        return sum(1 for (w, _) in self.docs if w == workspace_id)


class FakeStateRepo:
    def __init__(self, initial: dict | None = None) -> None:
        self.state = initial or {}

    async def get(self, workspace_id):
        return dict(self.state[workspace_id]) if workspace_id in self.state else None

    async def upsert(self, workspace_id, fields):
        cur = self.state.setdefault(workspace_id, {"workspace_id": workspace_id})
        cur.update(fields)

    async def all(self):
        return [dict(v, workspace_id=k) for k, v in self.state.items()]


class FakeSettingsService:
    def __init__(self, app_settings: AppSettings) -> None:
        self._s = app_settings

    async def get_settings(self):
        return self._s


class ArchiveServiceHarness(FreshArchiveService):
    def __init__(self, fakes: dict, *args) -> None:
        super().__init__(*args)
        self._fakes = fakes

    def _client_for(self, ws, limiter, sem):
        return self._fakes[ws.workspace_id]


def _doc(workspace_id: str, ticket_id: str, updated):
    return {
        "workspace_id": workspace_id,
        "ticket_id": ticket_id,
        "subject": f"Ticket {ticket_id}",
        "status": "resolved",
        "priority": "low",
        "requester": {},
        "description": "",
        "custom_fields": {},
        "created_at_fresh": updated,
        "updated_at_fresh": updated,
        "resolved_at": updated,
        "tags": [],
        "raw": {},
    }


def _app_settings(workspaces):
    # rate 0 disables the limiter so tests never actually sleep.
    return AppSettings(fresh_workspaces=workspaces, fresh_rate_limit_per_min=0, fresh_archive_since_months=1)


def _core_settings():
    return Settings(fresh_base_url="http://fs.local", fresh_api_key="key")


async def test_backfill_upserts_and_marks_done():
    now = utc_now()
    client = FakeArchiveClient([[_doc("w1", "1", now), _doc("w1", "2", now)]])  # one short page → done
    archive, state = FakeArchiveRepo(), FakeStateRepo()
    app_settings = _app_settings([FreshWorkspaceConfig(workspace_id="w1", name="WS1")])
    service = ArchiveServiceHarness(
        {"w1": client}, _core_settings(), FakeSettingsService(app_settings), archive, state
    )

    status = await service.backfill()

    assert await archive.count() == 2
    assert state.state["w1"]["backfill_done"] is True
    assert state.state["w1"]["in_progress"] is False
    assert status.total_archived == 2
    assert status.workspaces[0].archived_count == 2


async def test_backfill_resumes_from_checkpointed_cursor():
    cursor = utc_now() - timedelta(days=3)
    client = FakeArchiveClient([[_doc("w1", "1", utc_now())]])
    archive = FakeArchiveRepo()
    state = FakeStateRepo({"w1": {"backfill_window_cursor": cursor.isoformat()}})
    app_settings = _app_settings([FreshWorkspaceConfig(workspace_id="w1", name="WS1")])
    service = ArchiveServiceHarness(
        {"w1": client}, _core_settings(), FakeSettingsService(app_settings), archive, state
    )

    await service.backfill()

    first_updated_since = client.calls[0][0]
    assert first_updated_since.isoformat() == cursor.isoformat()


async def test_backfill_ignores_stale_backfill_since_and_uses_new_window():
    # A prior completed run left backfill_since recent (12-month window) and no
    # checkpoint; a new backfill with an older window must start from the new
    # `since`, not the sticky stored backfill_since.
    recent = utc_now() - timedelta(days=30)
    client = FakeArchiveClient([[_doc("5", "1", utc_now())]])
    archive = FakeArchiveRepo()
    state = FakeStateRepo({"5": {"backfill_since": recent.isoformat(), "backfill_window_cursor": None, "backfill_done": True}})
    app_settings = _app_settings([FreshWorkspaceConfig(workspace_id="5", name="IT")])
    service = ArchiveServiceHarness(
        {"5": client}, _core_settings(), FakeSettingsService(app_settings), archive, state
    )

    await service.backfill(workspace_id="5", since_months=120)

    first_updated_since = client.calls[0][0]
    # ~120 months ≈ 3600 days ago, far older than the stale 30-day backfill_since.
    assert (utc_now() - first_updated_since).days > 3000


async def test_pagination_advances_window_past_page_cap(monkeypatch):
    # Small page/cap so the window-advance path is exercised without 100s of docs.
    monkeypatch.setattr(svc_module, "PER_PAGE", 2)
    monkeypatch.setattr(svc_module, "PAGE_CAP", 1)
    base = utc_now()
    pages = [
        [_doc("w1", "1", base), _doc("w1", "2", base + timedelta(minutes=1))],  # full page → advance
        [_doc("w1", "3", base + timedelta(minutes=2)), _doc("w1", "4", base + timedelta(minutes=3))],  # advance
        [_doc("w1", "5", base + timedelta(minutes=4))],  # short → stop
    ]
    client = FakeArchiveClient(pages)
    archive, state = FakeArchiveRepo(), FakeStateRepo()
    app_settings = _app_settings([FreshWorkspaceConfig(workspace_id="w1", name="WS1")])
    service = ArchiveServiceHarness(
        {"w1": client}, _core_settings(), FakeSettingsService(app_settings), archive, state
    )

    await service.backfill()

    assert await archive.count() == 5
    assert len(client.calls) == 3


async def test_single_workspace_fallback_when_none_configured():
    client = FakeArchiveClient([[_doc("default", "1", utc_now())]])
    archive, state = FakeArchiveRepo(), FakeStateRepo()
    core = Settings(fresh_base_url="http://fs.local", fresh_api_key="key", fresh_workspace_id="default")
    service = ArchiveServiceHarness(
        {"default": client}, core, FakeSettingsService(_app_settings([])), archive, state
    )

    status = await service.backfill()

    assert await archive.count() == 1
    assert status.workspaces[0].workspace_id == "default"


async def test_backfill_skips_forbidden_workspace_and_continues():
    ok_client = FakeArchiveClient([[_doc("5", "1", utc_now())]])
    forbidden_client = FakeArchiveClient([], raise_status=403)
    archive, state = FakeArchiveRepo(), FakeStateRepo()
    app_settings = _app_settings([
        FreshWorkspaceConfig(workspace_id="5", name="IT"),
        FreshWorkspaceConfig(workspace_id="6", name="Logística"),
    ])
    service = ArchiveServiceHarness(
        {"5": ok_client, "6": forbidden_client}, _core_settings(), FakeSettingsService(app_settings), archive, state
    )

    status = await service.backfill()  # must not raise

    assert await archive.count() == 1  # IT still ingested
    assert state.state["5"]["backfill_done"] is True
    assert "sin permisos" in state.state["6"]["last_error"]
    forbidden = [w for w in status.workspaces if w.workspace_id == "6"][0]
    assert forbidden.last_error and "403" in forbidden.last_error


async def test_incremental_sync_advances_cursor():
    latest = utc_now()
    client = FakeArchiveClient([[_doc("w1", "1", latest)]])
    archive, state = FakeArchiveRepo(), FakeStateRepo()
    app_settings = _app_settings([FreshWorkspaceConfig(workspace_id="w1", name="WS1")])
    service = ArchiveServiceHarness(
        {"w1": client}, _core_settings(), FakeSettingsService(app_settings), archive, state
    )

    await service.sync_incremental()

    assert await archive.count() == 1
    assert state.state["w1"]["last_incremental_at"] is not None
