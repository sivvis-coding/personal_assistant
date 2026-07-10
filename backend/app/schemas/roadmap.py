from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.clickup import ClickUpTask


class RoadmapGroupPlan(BaseModel):
    """Represent one theme/epic group as produced by the LLM.

    Parameters:
        title: Short theme or epic name.
        summary: One-line description of what the group is about.
        task_ids: IDs of the tasks the LLM assigned to this group.

    Returns:
        Raw grouping plan for a single theme, before task rehydration.

    Edge cases:
        task_ids may contain unknown IDs; the service filters them out and
        rehydrates only real tasks. Any ID the LLM invents is ignored.
    """

    title: str
    summary: str = ""
    task_ids: list[str] = Field(default_factory=list)

    @field_validator("title", "summary", mode="before")
    @classmethod
    def coerce_to_str(cls, v: object) -> str:
        """Coerce non-string scalars/lists to a plain string."""
        if isinstance(v, list):
            return "\n".join(str(item) for item in v)
        return str(v) if not isinstance(v, str) else v

    @field_validator("task_ids", mode="before")
    @classmethod
    def coerce_ids_to_str(cls, v: object) -> list[str]:
        """Coerce the id list to a list of plain strings."""
        if v is None:
            return []
        if not isinstance(v, list):
            return [str(v)]
        return [str(item) for item in v]


class RoadmapPlan(BaseModel):
    """Represent the full LLM grouping plan for one list.

    Parameters:
        groups: Theme/epic groups produced by the LLM.

    Returns:
        Raw roadmap plan before task rehydration.

    Edge cases:
        Empty groups mean the LLM produced no classification; the service then
        falls back to a single unclassified group.
    """

    groups: list[RoadmapGroupPlan] = Field(default_factory=list)


class RoadmapGroupInput(BaseModel):
    """Represent a group as saved/edited from the UI or persistence.

    Parameters:
        list_id: ClickUp list this group belongs to.
        title: Theme or epic name.
        summary: One-line description of the group.
        task_ids: IDs of the tasks assigned to this group.

    Returns:
        Persisted/editable group structure (no rehydrated task data).

    Edge cases:
        Unknown IDs are ignored when the structure is rehydrated on read.
    """

    list_id: str = ""
    title: str
    summary: str = ""
    task_ids: list[str] = Field(default_factory=list)


class SaveRoadmapRequest(BaseModel):
    """Represent a request to persist an edited roadmap structure.

    Parameters:
        groups: Ordered groups (each tagged with its list_id) with assignments.

    Returns:
        Validated save request.

    Edge cases:
        The "Sin clasificar" group may be included or omitted; it is recomputed
        on read from tasks not present in any group of that list.
    """

    groups: list[RoadmapGroupInput] = Field(default_factory=list)


class RoadmapGroup(BaseModel):
    """Represent a rehydrated roadmap group returned to the frontend.

    Parameters:
        list_id: ClickUp list this group belongs to.
        title: Theme or epic name.
        summary: One-line description of the group.
        count: Number of tasks in the group.
        tasks: Full ClickUp tasks belonging to the group.

    Returns:
        API-ready roadmap group with real task data.

    Edge cases:
        The "Sin clasificar" group collects tasks the LLM did not assign.
    """

    list_id: str = ""
    title: str
    summary: str = ""
    count: int
    tasks: list[ClickUpTask]


class RoadmapListSection(BaseModel):
    """Represent one ClickUp list as a roadmap section.

    Parameters:
        list_id: ClickUp list ID.
        list_name: Display name of the list.
        summary: AI summary of the whole list (empty until generated).
        total_tasks: Number of tasks in this list.
        groups: Theme/epic groups within this list.

    Returns:
        Per-list roadmap section.

    Edge cases:
        summary stays empty until the user runs "Generar resúmenes".
    """

    list_id: str
    list_name: str
    summary: str = ""
    total_tasks: int
    groups: list[RoadmapGroup]


class RoadmapResponse(BaseModel):
    """Represent the generated roadmap returned by the API.

    Parameters:
        lists: One section per configured ClickUp list.
        total_tasks: Total number of source tasks across all lists.
        model: AI model used for grouping (or "mock").
        generated_at: UTC timestamp when the roadmap was generated.
        persisted: Whether a saved roadmap exists (false = never generated yet).

    Returns:
        Roadmap response for the frontend.

    Edge cases:
        With no persisted roadmap, lists is empty and persisted is false.
    """

    lists: list[RoadmapListSection]
    total_tasks: int
    model: str
    generated_at: datetime
    persisted: bool = True


class RoadmapSummaryTask(BaseModel):
    """Represent a task passed in for list summarization.

    Parameters:
        name: Task name.
        status: Task status name.
        description: Optional task description.

    Returns:
        Minimal task payload for summarization.

    Edge cases:
        Only the currently-visible (filtered) tasks are sent by the frontend.
    """

    name: str
    status: str = ""
    description: str | None = None


class RoadmapSummaryListInput(BaseModel):
    """Represent a list whose visible tasks should be summarized.

    Parameters:
        list_id: ClickUp list ID (echoed back to match the response).
        list_name: Display name of the list.
        tasks: Visible tasks in the list.

    Returns:
        List summarization input.

    Edge cases:
        Empty lists are skipped by the service.
    """

    list_id: str
    list_name: str = ""
    tasks: list[RoadmapSummaryTask] = Field(default_factory=list)


class SummarizeRoadmapRequest(BaseModel):
    """Represent a request to summarize each list from its visible tasks.

    Parameters:
        lists: Lists (with their filtered tasks) to summarize.

    Returns:
        Validated summarization request.

    Edge cases:
        Reflects the active status filter — summaries are not persisted.
    """

    lists: list[RoadmapSummaryListInput] = Field(default_factory=list)


class RoadmapListSummary(BaseModel):
    """Represent an AI summary for one list.

    Parameters:
        list_id: ClickUp list ID (echoed to match the request).
        summary: Short natural-language summary of the list's visible tasks.

    Returns:
        Per-list summary.

    Edge cases:
        Matched back to the list by list_id on the frontend.
    """

    list_id: str
    summary: str = ""

    @field_validator("summary", mode="before")
    @classmethod
    def coerce_to_str(cls, v: object) -> str:
        """Coerce non-string scalars/lists to a plain string."""
        if isinstance(v, list):
            return "\n".join(str(item) for item in v)
        return str(v) if not isinstance(v, str) else v


class RoadmapSummariesResponse(BaseModel):
    """Represent the AI summaries for the requested lists.

    Parameters:
        summaries: One summary per non-empty list.

    Returns:
        Summaries response for the frontend.

    Edge cases:
        With no lists, summaries is empty.
    """

    summaries: list[RoadmapListSummary] = Field(default_factory=list)
