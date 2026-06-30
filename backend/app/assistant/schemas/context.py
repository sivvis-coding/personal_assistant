from pydantic import BaseModel

from app.schemas.clickup import WeekTimeResponse
from app.schemas.ticket import Ticket


class AssistantContext(BaseModel):
    """Represent the operational context available to the assistant.

    Parameters:
        tickets: Tickets currently visible to the user.
        ticket_source: Source used to load tickets.
        week_time: Current week time report.
        existing_backlog_ticket_ids: Fresh ticket IDs already linked to ClickUp tasks.

    Returns:
        Context snapshot for assistant reasoning.

    Edge cases:
        Mock sources are preserved so the assistant can avoid presenting fake data as real.
    """

    tickets: list[Ticket]
    ticket_source: str
    week_time: WeekTimeResponse
    existing_backlog_ticket_ids: list[str]
