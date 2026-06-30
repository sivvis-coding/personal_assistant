from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    """Represent editable application integration settings.

    Parameters:
        fresh_base_url: Freshservice workspace URL.
        fresh_api_key: Freshservice API key.
        fresh_assigned_agent_id: Agent ID for "my tickets" filter.
        fresh_assigned_agent_field: Field used for assignment filter. Defaults to responder_id for Freshservice.
        clickup_api_key: ClickUp API key.
        clickup_team_id: ClickUp team ID.
        clickup_list_id: ClickUp list ID.
        openai_api_key: OpenAI API key.
        openai_model: OpenAI model name.

    Returns:
        Editable settings payload.

    Edge cases:
        Empty strings are valid and mean "not configured".
    """

    fresh_base_url: str = ""
    fresh_api_key: str = ""
    fresh_assigned_agent_id: str = ""
    fresh_assigned_agent_field: str = "agent_id"
    fresh_workspace_id: str = ""
    clickup_api_key: str = ""
    clickup_team_id: str = ""
    clickup_list_id: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4"

    model_config = {"extra": "ignore"}
