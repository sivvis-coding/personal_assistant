"""Input/output schemas for the Freshservice tool."""

from dataclasses import dataclass
from typing import Literal

from app.schemas.ticket import Ticket


@dataclass(frozen=True)
class ListTicketsInput:
    """Input for list_assigned_tickets operation."""

    scope: Literal["mine", "all"] = "mine"


@dataclass(frozen=True)
class GetTicketInput:
    """Input for get_ticket operation."""

    ticket_id: str


@dataclass(frozen=True)
class UpdateTicketInput:
    """Input for update_ticket operation."""

    ticket_id: str
    changes: dict[str, object]


@dataclass(frozen=True)
class ReplyTicketInput:
    """Input for reply_ticket operation."""

    ticket_id: str
    body: str


@dataclass(frozen=True)
class ResolveTicketInput:
    """Input for resolve_ticket operation."""

    ticket_id: str
    status: Literal["resolved", "closed"] = "resolved"


@dataclass(frozen=True)
class RequestInfoTicketInput:
    """Input for request_info_ticket: reply + set waiting-on-third-party."""

    ticket_id: str
    body: str


@dataclass(frozen=True)
class SearchTicketsInput:
    """Input for search_tickets operation."""

    query: str
    limit: int = 20


@dataclass(frozen=True)
class TicketListResult:
    """Output for list_assigned_tickets operation."""

    tickets: list[Ticket]
    source: str


@dataclass(frozen=True)
class TicketDetailResult:
    """Output for get_ticket operation."""

    ticket: Ticket
    source: str
