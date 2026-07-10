from typing import Any

from app.core.time import utc_now
from app.schemas.clickup import ClickUpTask
from app.schemas.roadmap import (
    RoadmapGroupInput,
    RoadmapGroupPlan,
    RoadmapPlan,
    RoadmapSummariesResponse,
    RoadmapListSummary,
    RoadmapSummaryListInput,
    RoadmapSummaryTask,
)
from app.schemas.settings import ClickUpListConfig
from app.services.roadmap_service import DEFAULT_LIST_ID, UNCLASSIFIED_TITLE, RoadmapService


class FakeClickUpClient:
    def __init__(self, tasks_by_list: dict[str, list[ClickUpTask]]) -> None:
        self._by_list = tasks_by_list

    async def list_tasks_for(self, list_id: str, list_name: str | None = None) -> list[ClickUpTask]:
        return self._by_list.get(list_id, [])

    async def list_tasks(self) -> list[ClickUpTask]:
        return [t for tasks in self._by_list.values() for t in tasks]


class FakeOpenAIClient:
    def __init__(self, plans_by_list: dict[str, RoadmapPlan] | None = None, model: str = "test-model") -> None:
        self._plans = plans_by_list or {}
        self.model = model
        self.received_by_list: dict[str | None, list[ClickUpTask]] = {}
        self.summarize_received: list[RoadmapSummaryListInput] | None = None

    async def generate_roadmap(self, tasks: list[ClickUpTask]) -> RoadmapPlan:
        list_id = tasks[0].list_id if tasks else None
        self.received_by_list[list_id] = tasks
        return self._plans.get(list_id or "", RoadmapPlan(groups=[]))

    async def summarize_roadmap_lists(self, lists: list[RoadmapSummaryListInput]) -> RoadmapSummariesResponse:
        self.summarize_received = lists
        return RoadmapSummariesResponse(
            summaries=[RoadmapListSummary(list_id=entry.list_id, summary=f"sum-{entry.list_id}") for entry in lists]
        )


class FakeSettings:
    def __init__(self, lists: list[ClickUpListConfig]) -> None:
        self.clickup_lists = lists


class FakeSettingsService:
    def __init__(self, lists: list[ClickUpListConfig]) -> None:
        self._lists = lists

    async def get_settings(self) -> FakeSettings:
        return FakeSettings(self._lists)


class FakeRoadmapRepository:
    def __init__(self, doc: dict[str, Any] | None = None) -> None:
        self.doc = doc

    async def find_current(self) -> dict[str, Any] | None:
        return self.doc

    async def save_current(self, groups: list[dict[str, Any]], model: str) -> None:
        generated_at = self.doc.get("generated_at", utc_now()) if self.doc else utc_now()
        self.doc = {"slug": "current", "groups": groups, "model": model, "generated_at": generated_at}

    async def touch_generated_at(self) -> None:
        if self.doc is not None:
            self.doc["generated_at"] = utc_now()


def _task(task_id: str, name: str, status: str, list_id: str, list_name: str) -> ClickUpTask:
    return ClickUpTask(id=task_id, name=name, status=status, list_id=list_id, list_name=list_name)


def _tasks_by_list() -> dict[str, list[ClickUpTask]]:
    return {
        "L1": [
            _task("t1", "Login", "pending", "L1", "Product"),
            _task("t2", "Signup", "in progress", "L1", "Product"),
            _task("t3", "Old feature", "done", "L1", "Product"),
        ],
        "L2": [
            _task("b1", "Crash on save", "pending", "L2", "Bugs"),
            _task("b2", "UI glitch", "ready to define", "L2", "Bugs"),
        ],
    }


TWO_LISTS = [ClickUpListConfig(id="L1", name="Product"), ClickUpListConfig(id="L2", name="Bugs")]


def _service(tasks_by_list, plans=None, doc=None, lists=TWO_LISTS):
    ai = FakeOpenAIClient(plans)
    repo = FakeRoadmapRepository(doc)
    settings_service = FakeSettingsService(lists)
    return RoadmapService(FakeClickUpClient(tasks_by_list), ai, repo, settings_service), ai, repo


def _section(result, list_id):
    return next(s for s in result.lists if s.list_id == list_id)


def _group(section, title):
    return next(g for g in section.groups if g.title == title)


# --- generate() -------------------------------------------------------------

async def test_generate_splits_into_one_section_per_list() -> None:
    plans = {
        "L1": RoadmapPlan(groups=[RoadmapGroupPlan(title="Auth", task_ids=["t1", "t2"])]),
        "L2": RoadmapPlan(groups=[RoadmapGroupPlan(title="Crashes", task_ids=["b1"])]),
    }
    service, ai, repo = _service(_tasks_by_list(), plans)

    result = await service.generate()

    assert [s.list_id for s in result.lists] == ["L1", "L2"]
    assert result.total_tasks == 5
    assert result.persisted is True
    # L1: Auth [t1,t2] + unclassified [t3]
    l1 = _section(result, "L1")
    assert [t.id for t in _group(l1, "Auth").tasks] == ["t1", "t2"]
    assert [t.id for t in _group(l1, UNCLASSIFIED_TITLE).tasks] == ["t3"]
    # L2: Crashes [b1] + unclassified [b2]
    l2 = _section(result, "L2")
    assert [t.id for t in _group(l2, "Crashes").tasks] == ["b1"]
    assert [t.id for t in _group(l2, UNCLASSIFIED_TITLE).tasks] == ["b2"]
    # each list summarized independently by the LLM
    assert set(ai.received_by_list.keys()) == {"L1", "L2"}
    # persisted structures carry list_id, no unclassified persisted
    assert all("list_id" in g for g in repo.doc["groups"])
    assert UNCLASSIFIED_TITLE not in [g["title"] for g in repo.doc["groups"]]


async def test_generate_falls_back_to_single_list_when_none_configured() -> None:
    service, _, _ = _service(_tasks_by_list(), lists=[])

    result = await service.generate()

    assert [s.list_id for s in result.lists] == [DEFAULT_LIST_ID]
    assert result.total_tasks == 5


# --- get_persisted() --------------------------------------------------------

async def test_get_persisted_not_persisted_when_empty() -> None:
    service, _, _ = _service(_tasks_by_list(), doc=None)

    result = await service.get_persisted()

    assert result.persisted is False
    assert result.lists == []
    assert result.total_tasks == 5


async def test_get_persisted_rehydrates_per_list_and_recomputes_unclassified() -> None:
    doc = {
        "groups": [{"list_id": "L1", "title": "Auth", "summary": "", "task_ids": ["t1"]}],
        "model": "saved-model",
        "generated_at": utc_now(),
    }
    service, ai, _ = _service(_tasks_by_list(), doc=doc)

    result = await service.get_persisted()

    assert result.model == "saved-model"
    assert ai.received_by_list == {}  # no LLM call on read
    l1 = _section(result, "L1")
    assert [t.id for t in _group(l1, "Auth").tasks] == ["t1"]
    assert {t.id for t in _group(l1, UNCLASSIFIED_TITLE).tasks} == {"t2", "t3"}
    # L2 had no stored groups -> everything unclassified
    l2 = _section(result, "L2")
    assert {t.id for t in _group(l2, UNCLASSIFIED_TITLE).tasks} == {"b1", "b2"}


# --- save() -----------------------------------------------------------------

async def test_save_persists_list_id_and_recomputes_unclassified() -> None:
    doc = {"groups": [], "model": "saved-model", "generated_at": utc_now()}
    service, _, repo = _service(_tasks_by_list(), doc=doc)

    edited = [
        RoadmapGroupInput(list_id="L1", title="Auth", task_ids=["t1", "t2"]),
        RoadmapGroupInput(list_id="L2", title="Crashes", task_ids=["b1"]),
    ]
    result = await service.save(edited)

    assert result.model == "saved-model"
    assert {g["list_id"] for g in repo.doc["groups"]} == {"L1", "L2"}
    assert {t.id for t in _group(_section(result, "L1"), UNCLASSIFIED_TITLE).tasks} == {"t3"}
    assert {t.id for t in _group(_section(result, "L2"), UNCLASSIFIED_TITLE).tasks} == {"b2"}


async def test_save_drops_cross_list_task_ids() -> None:
    doc = {"groups": [], "model": "m", "generated_at": utc_now()}
    service, _, _ = _service(_tasks_by_list(), doc=doc)

    # t1 belongs to L1, but is placed under an L2 group -> must be dropped
    edited = [RoadmapGroupInput(list_id="L2", title="Wrong", task_ids=["t1", "b1"])]
    result = await service.save(edited)

    wrong = _group(_section(result, "L2"), "Wrong")
    assert [t.id for t in wrong.tasks] == ["b1"]


# --- summarize() ------------------------------------------------------------

async def test_summarize_returns_one_summary_per_non_empty_list() -> None:
    service, ai, _ = _service(_tasks_by_list())

    summaries = await service.summarize(
        [
            RoadmapSummaryListInput(list_id="L1", list_name="Product", tasks=[RoadmapSummaryTask(name="x", status="pending")]),
            RoadmapSummaryListInput(list_id="L2", list_name="Bugs", tasks=[]),  # empty -> skipped
        ]
    )

    assert [s.list_id for s in summaries.summaries] == ["L1"]
    assert ai.summarize_received is not None
    assert [entry.list_id for entry in ai.summarize_received] == ["L1"]
