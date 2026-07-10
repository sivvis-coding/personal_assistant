from typing import Any

from app.core.time import utc_now
from app.integrations.clickup import ClickUpClient
from app.integrations.openai_client import OpenAIClient
from app.repositories.roadmap_repository import RoadmapRepository
from app.schemas.clickup import ClickUpTask
from app.schemas.roadmap import (
    RoadmapGroup,
    RoadmapGroupInput,
    RoadmapListSection,
    RoadmapResponse,
    RoadmapSummariesResponse,
    RoadmapSummaryListInput,
)
from app.services.settings_service import SettingsService

UNCLASSIFIED_TITLE = "Sin clasificar"
UNCLASSIFIED_SUMMARY = "Tareas nuevas o sin agrupar. Arrástralas al tema que corresponda."

# Fallback pseudo-list used when no lists are configured in app settings.
DEFAULT_LIST_ID = "default"
DEFAULT_LIST_NAME = "ClickUp"

ListWithTasks = tuple[str, str, list[ClickUpTask]]


class RoadmapService:
    """Generate, persist, and edit a per-list themed roadmap of ClickUp tasks.

    Parameters:
        clickup_client: ClickUp integration client (task source).
        openai_client: OpenAI integration client (LLM grouping + summaries).
        roadmap_repository: Persistence for the current roadmap structure.
        settings_service: Source of the configured ClickUp lists.

    Returns:
        Service producing and storing a roadmap split by ClickUp list.

    Edge cases:
        Tasks are pulled from every configured list (AppSettings.clickup_lists);
        if none are configured, it falls back to the single legacy list.
        Only the grouping structure is persisted; task data is rehydrated live.
    """

    def __init__(
        self,
        clickup_client: ClickUpClient,
        openai_client: OpenAIClient,
        roadmap_repository: RoadmapRepository,
        settings_service: SettingsService,
    ) -> None:
        self._clickup_client = clickup_client
        self._openai_client = openai_client
        self._roadmap_repository = roadmap_repository
        self._settings_service = settings_service

    async def _fetch_lists(self) -> list[ListWithTasks]:
        """Return (list_id, list_name, tasks) for every configured list.

        Parameters:
            None.

        Returns:
            One entry per configured ClickUp list, with its live tasks.

        Edge cases:
            With no configured lists, falls back to the single legacy list
            (settings.clickup_list_id) under a "ClickUp" pseudo-section.
        """
        app_settings = await self._settings_service.get_settings()
        configs = app_settings.clickup_lists
        if configs:
            result: list[ListWithTasks] = []
            for config in configs:
                tasks = await self._clickup_client.list_tasks_for(config.id, config.name)
                result.append((config.id, config.name, tasks))
            return result

        legacy = await self._clickup_client.list_tasks()
        tagged = [t.model_copy(update={"list_id": DEFAULT_LIST_ID, "list_name": DEFAULT_LIST_NAME}) for t in legacy]
        return [(DEFAULT_LIST_ID, DEFAULT_LIST_NAME, tagged)]

    def _rehydrate_list(
        self, list_id: str, list_name: str, structures: list[dict[str, Any]], tasks: list[ClickUpTask]
    ) -> RoadmapListSection:
        """Build one list section from its saved group structures and live tasks.

        Parameters:
            list_id: ClickUp list ID.
            list_name: Display name of the list.
            structures: Persisted groups for this list ({title, summary, task_ids}).
            tasks: Live tasks belonging to this list.

        Returns:
            Rehydrated list section; leftovers land in "Sin clasificar".

        Edge cases:
            Empty non-unclassified groups are kept so manual columns survive a
            reload. IDs no longer present in the list are dropped silently.
        """
        tasks_by_id = {task.id: task for task in tasks}
        groups: list[RoadmapGroup] = []
        assigned: set[str] = set()
        for structure in structures:
            if structure.get("title") == UNCLASSIFIED_TITLE:
                continue
            group_tasks = []
            for task_id in structure.get("task_ids", []):
                task = tasks_by_id.get(task_id)
                if task is None or task_id in assigned:
                    continue
                assigned.add(task_id)
                group_tasks.append(task)
            groups.append(
                RoadmapGroup(
                    list_id=list_id,
                    title=structure.get("title", ""),
                    summary=structure.get("summary", ""),
                    count=len(group_tasks),
                    tasks=group_tasks,
                )
            )

        leftovers = [task for task in tasks if task.id not in assigned]
        if leftovers:
            groups.append(
                RoadmapGroup(
                    list_id=list_id,
                    title=UNCLASSIFIED_TITLE,
                    summary=UNCLASSIFIED_SUMMARY,
                    count=len(leftovers),
                    tasks=leftovers,
                )
            )
        return RoadmapListSection(
            list_id=list_id,
            list_name=list_name,
            summary="",
            total_tasks=len(tasks),
            groups=groups,
        )

    def _assemble(self, structures: list[dict[str, Any]], lists: list[ListWithTasks]) -> list[RoadmapListSection]:
        """Group persisted structures by list and rehydrate each section."""
        sections = []
        for list_id, list_name, tasks in lists:
            list_structures = [s for s in structures if s.get("list_id", "") == list_id]
            sections.append(self._rehydrate_list(list_id, list_name, list_structures, tasks))
        return sections

    def _response(
        self, sections: list[RoadmapListSection], lists: list[ListWithTasks], model: str, generated_at: Any, persisted: bool
    ) -> RoadmapResponse:
        total = sum(len(tasks) for _, _, tasks in lists)
        return RoadmapResponse(
            lists=sections,
            total_tasks=total,
            model=model,
            generated_at=generated_at,
            persisted=persisted,
        )

    async def get_persisted(self) -> RoadmapResponse:
        """Return the saved roadmap rehydrated with live tasks, split by list.

        Parameters:
            None.

        Returns:
            Rehydrated roadmap, or persisted=False when never generated.

        Edge cases:
            New tasks appear under each list's "Sin clasificar" with no LLM call.
        """
        doc = await self._roadmap_repository.find_current()
        lists = await self._fetch_lists()
        if doc is None:
            return self._response([], lists, self._openai_client.model, utc_now(), persisted=False)
        sections = self._assemble(doc.get("groups", []), lists)
        return self._response(
            sections,
            lists,
            doc.get("model", self._openai_client.model),
            doc.get("generated_at", utc_now()),
            persisted=True,
        )

    async def generate(self) -> RoadmapResponse:
        """Group each list's tasks by theme via the LLM, persist, and return.

        Parameters:
            None.

        Returns:
            Freshly generated and saved roadmap split by list.

        Edge cases:
            Overwrites any manual edits. One LLM grouping call per list. Empty
            groups are not persisted; LLM-invented/duplicate IDs are dropped.
        """
        lists = await self._fetch_lists()
        structures: list[dict[str, Any]] = []
        for list_id, _list_name, tasks in lists:
            plan = await self._openai_client.generate_roadmap(tasks)
            known_ids = {task.id for task in tasks}
            assigned: set[str] = set()
            for group_plan in plan.groups:
                ids = []
                for task_id in group_plan.task_ids:
                    if task_id in known_ids and task_id not in assigned:
                        assigned.add(task_id)
                        ids.append(task_id)
                if ids:
                    structures.append(
                        {"list_id": list_id, "title": group_plan.title, "summary": group_plan.summary, "task_ids": ids}
                    )

        await self._roadmap_repository.save_current(structures, self._openai_client.model)
        await self._roadmap_repository.touch_generated_at()

        sections = self._assemble(structures, lists)
        return self._response(sections, lists, self._openai_client.model, utc_now(), persisted=True)

    async def save(self, groups_input: list[RoadmapGroupInput]) -> RoadmapResponse:
        """Persist an edited roadmap structure and return it rehydrated.

        Parameters:
            groups_input: Ordered groups (each tagged with list_id) from the UI.

        Returns:
            Rehydrated, saved roadmap split by list.

        Edge cases:
            The "Sin clasificar" group is not persisted (recomputed on read).
            Unknown/duplicate IDs are dropped per list; empty user groups kept.
        """
        doc = await self._roadmap_repository.find_current()
        model = doc.get("model", self._openai_client.model) if doc else self._openai_client.model
        generated_at = doc.get("generated_at", utc_now()) if doc else utc_now()

        lists = await self._fetch_lists()
        known_by_list = {list_id: {t.id for t in tasks} for list_id, _, tasks in lists}

        structures: list[dict[str, Any]] = []
        assigned_by_list: dict[str, set[str]] = {}
        for group in groups_input:
            if group.title == UNCLASSIFIED_TITLE:
                continue
            known = known_by_list.get(group.list_id, set())
            assigned = assigned_by_list.setdefault(group.list_id, set())
            ids = []
            for task_id in group.task_ids:
                if task_id in known and task_id not in assigned:
                    assigned.add(task_id)
                    ids.append(task_id)
            structures.append({"list_id": group.list_id, "title": group.title, "summary": group.summary, "task_ids": ids})

        await self._roadmap_repository.save_current(structures, model)
        sections = self._assemble(structures, lists)
        return self._response(sections, lists, model, generated_at, persisted=True)

    async def summarize(self, lists_input: list[RoadmapSummaryListInput]) -> RoadmapSummariesResponse:
        """Return an AI summary for each list from its visible tasks.

        Parameters:
            lists_input: Lists with their currently-visible (filtered) tasks.

        Returns:
            One summary per non-empty list.

        Edge cases:
            Summaries reflect the active filter and are not persisted.
        """
        non_empty = [entry for entry in lists_input if entry.tasks]
        if not non_empty:
            return RoadmapSummariesResponse(summaries=[])
        return await self._openai_client.summarize_roadmap_lists(non_empty)
