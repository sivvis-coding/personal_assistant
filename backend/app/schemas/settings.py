import re

from pydantic import BaseModel, field_validator

# ClickUp's "Copy link" on some views (notably the Home > Personal List feature)
# yields a composite view id such as "6-901505357877-1" (view type - list id -
# view sequence), or a full URL ending in that segment — not the plain numeric
# list id the REST API (/api/v2/list/{list_id}) expects. Requesting that composite
# value directly returns a 400 Bad Request from ClickUp.
_CLICKUP_VIEW_ID_SEGMENT = re.compile(r"^\d+-(\d+)-\d+$")


def _normalize_clickup_list_id(value: str) -> str:
    """Extract a plain numeric ClickUp list id from a pasted URL or view id.

    Parameters:
        value: Raw value pasted by the user (list id, view id, or full URL).

    Returns:
        The plain list id when a composite view-id pattern is recognized,
        otherwise the trimmed input unchanged.

    Edge cases:
        Unrecognized formats are passed through as-is rather than mangled,
        so a genuinely correct plain list id is never altered.
    """
    trimmed = value.strip()
    if not trimmed:
        return trimmed
    segment = trimmed.rstrip("/").split("/")[-1]
    match = _CLICKUP_VIEW_ID_SEGMENT.match(segment)
    return match.group(1) if match else trimmed


class ClickUpCustomFieldConfig(BaseModel):
    """Describe a single ClickUp custom field for agent consumption.

    Parameters:
        field_id: ClickUp custom field UUID.
        field_name: Human-readable field name.
        description: Instructions for the agent on what value to put here.
    """

    field_id: str
    field_name: str
    description: str = ""


class ClickUpListConfig(BaseModel):
    """Configure one ClickUp list for routing and field population.

    Parameters:
        id: ClickUp list ID.
        name: Display name shown in the UI.
        description: Routing hint for the agent (e.g. "Use for bug reports").
        custom_fields: Documented fields the agent should populate.
    """

    id: str
    name: str
    description: str = ""
    custom_fields: list[ClickUpCustomFieldConfig] = []


class FreshWorkspaceConfig(BaseModel):
    """Configure one Freshservice workspace for history harvesting.

    Parameters:
        workspace_id: Freshservice numeric workspace ID (sent as workspace_id query param).
        name: Display name shown in the UI.
        base_url: Optional per-workspace base URL override. Empty → use the global
            fresh_base_url. Lets a second, separate Freshservice instance be added
            without a redesign.
        api_key: Optional per-workspace API key override. Empty → use the global
            fresh_api_key.

    Edge cases:
        Empty base_url/api_key fall back to the global Freshservice credentials so
        the common "two workspaces, same instance" case needs only a workspace_id.
    """

    workspace_id: str
    name: str
    base_url: str = ""
    api_key: str = ""


class AppSettings(BaseModel):
    """Represent editable application integration settings.

    Parameters:
        fresh_base_url: Freshservice workspace URL.
        fresh_api_key: Freshservice API key.
        fresh_assigned_agent_id: Agent ID for "my tickets" filter.
        fresh_assigned_agent_field: Field used for assignment filter. Defaults to agent_id for Freshservice.
        fresh_workspace_id: Freshservice workspace ID.
        fresh_workspaces: Workspaces to harvest for the Insights history archive.
            When empty, the archive falls back to a single workspace synthesized
            from fresh_workspace_id.
        fresh_archive_since_months: How many months back the historic backfill reaches.
        fresh_rate_limit_per_min: Max Freshservice requests per minute during harvesting.
        clickup_api_key: ClickUp API key.
        clickup_team_id: ClickUp team ID.
        clickup_lists: Configured ClickUp lists with routing descriptions and field docs.
        clickup_personal_list_id: Dedicated ClickUp list ID used for daily hour imputation tasks.
            Often ClickUp's own "Personal List" feature (Home > My Tasks > Personal List), which
            lives outside the Space/Folder hierarchy and therefore cannot be discovered via the
            team/space/folder list-discovery endpoints — the user must paste its ID manually
            (ClickUp sidebar > right-click the list > Copy link > take the ID from the URL).
        clickup_personal_list_name: Display name for the personal list, shown in the UI.
        agent_system_prompt: Custom behavioral instructions appended to the base agent prompt.
        openai_api_key: OpenAI API key.
        openai_model: OpenAI model name.

    Returns:
        Editable settings payload.

    Edge cases:
        Empty strings are valid and mean "not configured".
        clickup_lists replaces the legacy clickup_list_id field.
        clickup_personal_list_id is a single dedicated list, distinct from the clickup_lists
        routing table used for ticket-derived tasks.
    """

    fresh_base_url: str = ""
    fresh_api_key: str = ""
    fresh_assigned_agent_id: str = ""
    fresh_assigned_agent_field: str = "agent_id"
    fresh_workspace_id: str = ""
    fresh_workspaces: list[FreshWorkspaceConfig] = []
    fresh_archive_since_months: int = 120
    fresh_rate_limit_per_min: int = 80
    clickup_api_key: str = ""
    clickup_team_id: str = ""
    clickup_lists: list[ClickUpListConfig] = []
    clickup_personal_list_id: str = ""
    clickup_personal_list_name: str = ""
    agent_system_prompt: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4"

    model_config = {"extra": "ignore"}

    @field_validator("clickup_personal_list_id")
    @classmethod
    def _validate_clickup_personal_list_id(cls, value: str) -> str:
        """Normalize a pasted ClickUp view id/URL into a plain list id."""
        return _normalize_clickup_list_id(value)


class ClickUpFieldInput(BaseModel):
    """A field to send to the suggestion endpoint."""

    field_id: str
    field_name: str
    type_: str = ""


class ClickUpSuggestRequest(BaseModel):
    """Request body for AI-generated ClickUp descriptions."""

    list_name: str
    existing_description: str = ""
    fields: list[ClickUpFieldInput] = []


class ClickUpFieldSuggestion(BaseModel):
    """AI-generated description for a single custom field."""

    field_id: str
    description: str


class ClickUpSuggestResponse(BaseModel):
    """AI-generated suggestions for a ClickUp list configuration."""

    routing_description: str
    field_descriptions: list[ClickUpFieldSuggestion] = []
