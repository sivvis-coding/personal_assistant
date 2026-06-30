from pydantic import BaseModel

from app.schemas.clickup import WeekTimeResponse
from app.schemas.settings import ClickUpListConfig
from app.schemas.ticket import Ticket


class AssistantContext(BaseModel):
    """Represent the operational context available to the assistant.

    Parameters:
        tickets: Tickets currently visible to the user.
        ticket_source: Source used to load tickets.
        week_time: Current week time report.
        existing_backlog_ticket_ids: Fresh ticket IDs already linked to ClickUp tasks.
        clickup_lists: Configured ClickUp lists with routing descriptions and field docs.
        agent_system_prompt: Custom behavioral instructions appended to the base agent prompt.

    Returns:
        Context snapshot for assistant reasoning.

    Edge cases:
        Mock sources are preserved so the assistant can avoid presenting fake data as real.
        clickup_lists is empty when not yet configured.
    """

    tickets: list[Ticket]
    ticket_source: str
    week_time: WeekTimeResponse
    existing_backlog_ticket_ids: list[str]
    clickup_lists: list[ClickUpListConfig] = []
    agent_system_prompt: str = ""
