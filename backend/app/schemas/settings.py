from pydantic import BaseModel


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


class AppSettings(BaseModel):
    """Represent editable application integration settings.

    Parameters:
        fresh_base_url: Freshservice workspace URL.
        fresh_api_key: Freshservice API key.
        fresh_assigned_agent_id: Agent ID for "my tickets" filter.
        fresh_assigned_agent_field: Field used for assignment filter. Defaults to agent_id for Freshservice.
        fresh_workspace_id: Freshservice workspace ID.
        clickup_api_key: ClickUp API key.
        clickup_team_id: ClickUp team ID.
        clickup_lists: Configured ClickUp lists with routing descriptions and field docs.
        agent_system_prompt: Custom behavioral instructions appended to the base agent prompt.
        openai_api_key: OpenAI API key.
        openai_model: OpenAI model name.

    Returns:
        Editable settings payload.

    Edge cases:
        Empty strings are valid and mean "not configured".
        clickup_lists replaces the legacy clickup_list_id field.
    """

    fresh_base_url: str = ""
    fresh_api_key: str = ""
    fresh_assigned_agent_id: str = ""
    fresh_assigned_agent_field: str = "agent_id"
    fresh_workspace_id: str = ""
    clickup_api_key: str = ""
    clickup_team_id: str = ""
    clickup_lists: list[ClickUpListConfig] = []
    agent_system_prompt: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4"

    model_config = {"extra": "ignore"}


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
