"""Schemas for the Freshservice history archive and knowledge base (Insights).

Two families, mirroring the roadmap split:
- LLM-plan (raw) models validated straight off the model output.
- API / persistence / response models served to the frontend.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# --- Per-ticket signature (the "map" phase = per-ticket ficha) ---------------


class TicketSignature(BaseModel):
    """Compact LLM summary of a single ticket, cached on the archive document.

    Parameters:
        problem: One-line statement of the reported problem.
        category: Short normalized category/bucket (used for pre-grouping).
        root_cause: Diagnosed root cause, or "unknown" when not evident.
        resolution: How it was resolved, or "unresolved".
        product_area: Affected product/module area.
        tags: Free-form keyword tags for clustering.

    Edge cases:
        All fields are plain strings so the model output validates even when a
        field is unknown; tags default to an empty list.
    """

    problem: str
    category: str
    root_cause: str = "unknown"
    resolution: str = "unresolved"
    product_area: str = ""
    tags: list[str] = []

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_tags(cls, value: object) -> list[str]:
        """Accept a scalar, comma string, or list and normalize to list[str]."""
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        if isinstance(value, list):
            return [str(part).strip() for part in value if str(part).strip()]
        return [str(value)]


# --- Archive ticket (served in the "Tickets" tab) ----------------------------


class TicketRef(BaseModel):
    """Reference to an archived ticket used inside knowledge entries."""

    workspace_id: str
    ticket_id: str
    subject: str = ""


class ArchivedTicket(BaseModel):
    """An archived ticket with its (optional) signature, for the Tickets tab.

    Edge cases:
        signature is None until the knowledge map phase has processed it.
    """

    workspace_id: str
    ticket_id: str
    subject: str
    status: str
    priority: str = "unknown"
    created_at_fresh: datetime | None = None
    updated_at_fresh: datetime | None = None
    signature: TicketSignature | None = None


class ArchivedTicketsResponse(BaseModel):
    """Paginated slice of archived tickets."""

    items: list[ArchivedTicket]
    total: int
    skip: int
    limit: int


# --- Harvest status (the "Estado" tab) ---------------------------------------


class WorkspaceHarvestStatus(BaseModel):
    """Harvest progress and stats for a single workspace."""

    workspace_id: str
    name: str = ""
    backfill_done: bool = False
    backfill_since: datetime | None = None
    last_incremental_at: datetime | None = None
    in_progress: bool = False
    fetched: int = 0
    upserted: int = 0
    convos: int = 0
    archived_count: int = 0
    last_error: str | None = None


class HarvestStatus(BaseModel):
    """Aggregate harvest status across configured workspaces."""

    workspaces: list[WorkspaceHarvestStatus]
    total_archived: int


# --- Knowledge base (the "Conocimiento" tab) ---------------------------------


class ClusterGroup(BaseModel):
    """One cluster of tickets sharing a theme (raw LLM reduce output)."""

    title: str
    ticket_keys: list[str] = []

    @field_validator("ticket_keys", mode="before")
    @classmethod
    def _coerce_keys(cls, value: object) -> list[str]:
        """Accept scalar/list and normalize to list[str] of ticket keys."""
        if value is None:
            return []
        if isinstance(value, list):
            return [str(part) for part in value]
        return [str(value)]


class ClusterPlan(BaseModel):
    """Raw LLM clustering plan: theme titles + the ticket keys they contain."""

    clusters: list[ClusterGroup] = []


class ConsolidationGroup(BaseModel):
    """One canonical theme merging several fragmented candidate cluster titles."""

    canonical_title: str
    members: list[str] = []

    @field_validator("members", mode="before")
    @classmethod
    def _coerce_members(cls, value: object) -> list[str]:
        """Accept scalar/list and normalize to list[str] of member titles."""
        if value is None:
            return []
        if isinstance(value, list):
            return [str(part) for part in value]
        return [str(value)]


class ConsolidationPlan(BaseModel):
    """Raw LLM consolidation plan: candidate titles merged into canonical themes."""

    groups: list[ConsolidationGroup] = []


class ThemeDoc(BaseModel):
    """Generated prose documentation for one theme (raw LLM write output)."""

    title: str
    summary: str
    symptoms: str = ""
    root_causes: str = ""
    resolution_steps: str = ""


class KnowledgeTheme(BaseModel):
    """A persisted theme document with computed frequency and references."""

    title: str
    summary: str
    symptoms: str = ""
    root_causes: str = ""
    resolution_steps: str = ""
    frequency: int = 0
    workspaces: list[str] = []
    ticket_refs: list[TicketRef] = []


class RecurringIssue(BaseModel):
    """A recurring problem bucket with how often it appears."""

    label: str
    count: int
    ticket_refs: list[TicketRef] = []


class CategoryMetric(BaseModel):
    """Structured per-category metrics for a department (computed, not LLM)."""

    category: str
    volume: int
    avg_resolution_hours: float | None = None
    reopen_rate: float | None = None


class Bottleneck(BaseModel):
    """A place where work piles up or stalls within a department."""

    title: str
    description: str
    severity: str = "medium"
    category: str = ""
    ticket_refs: list[TicketRef] = []


class AutomationOpportunity(BaseModel):
    """A repetitive/low-value pattern that could be automated or self-served."""

    title: str
    description: str
    rationale: str = ""
    category: str = ""
    ticket_refs: list[TicketRef] = []


class DepartmentKnowledge(BaseModel):
    """The full analysis for one department (Freshservice workspace)."""

    workspace_id: str
    name: str = ""
    total_tickets: int = 0
    themes: list[KnowledgeTheme] = []
    recurring: list[RecurringIssue] = []
    bottlenecks: list[Bottleneck] = []
    automation: list[AutomationOpportunity] = []
    metrics: list[CategoryMetric] = []


# --- LLM-plan (raw) analysis models ------------------------------------------


class BottleneckPlan(BaseModel):
    """Raw LLM bottleneck (references a category so refs can be attached)."""

    title: str
    description: str
    severity: str = "medium"
    category: str = ""


class AutomationPlan(BaseModel):
    """Raw LLM automation opportunity (references a category)."""

    title: str
    description: str
    rationale: str = ""
    category: str = ""


class DepartmentAnalysisPlan(BaseModel):
    """Raw LLM department analysis: bottlenecks + automation opportunities."""

    bottlenecks: list[BottleneckPlan] = []
    automation: list[AutomationPlan] = []


class KnowledgeResponse(BaseModel):
    """The persisted knowledge base served to the UI, split by department."""

    departments: list[DepartmentKnowledge] = []
    model: str = ""
    generated_at: datetime | None = None
    persisted: bool = False


# --- Requests ----------------------------------------------------------------


class WorkspaceOption(BaseModel):
    """A Freshservice workspace (id + name) for discovery/config UI."""

    workspace_id: str
    name: str = ""


class WorkspacesResponse(BaseModel):
    """Available (from the Freshservice API) and configured workspaces."""

    available: list[WorkspaceOption] = []
    configured: list[WorkspaceOption] = []


class BackfillRequest(BaseModel):
    """Optional parameters for a historic backfill run."""

    workspace_id: str | None = Field(default=None, description="Limit to a single workspace.")
    since_months: int | None = Field(default=None, description="Override the configured window.")


class GenerateKnowledgeRequest(BaseModel):
    """Scope for a knowledge-generation run.

    Empty/omitted → the service uses all statuses so bottlenecks over open and
    pending tickets are also captured.
    """

    statuses: list[str] | None = None
