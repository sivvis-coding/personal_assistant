from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

TicketStatus = Literal[
    "open",
    "pending",
    "resolved",
    "closed",
    "waiting on customer",
    "waiting on third party",
    "unknown",
]

TicketPriority = Literal["low", "medium", "high", "urgent", "unknown"]

SlaStatus = Literal["ok", "at_risk", "breached", "none"]

ConversationKind = Literal["customer_reply", "agent_reply", "private_note"]


class SlaHint(BaseModel):
    """Represent computed SLA state for a ticket.

    Parameters:
        status: ok, at_risk, breached, or none when no due date exists.
        due_at: The relevant due datetime used for the computation.
        minutes_remaining: Minutes until breach; negative when already breached.

    Returns:
        SLA hint value object.

    Edge cases:
        minutes_remaining is None when status is none.
    """

    status: SlaStatus
    due_at: datetime | None = None
    minutes_remaining: int | None = None


class TicketConversation(BaseModel):
    """Represent a single conversation entry on a Fresh ticket.

    Parameters:
        id: Conversation entry identifier.
        kind: Type of entry: customer_reply, agent_reply, or private_note.
        body_text: Plain-text body, preferred over HTML.
        body_html: Raw HTML body from Fresh (not rendered directly in UI).
        from_email: Email address of the sender.
        incoming: Whether the entry originated from the customer.
        private: Whether the entry is a private note invisible to the requester.
        created_at: Creation timestamp.
        raw: Original payload.

    Returns:
        Normalized conversation entry.

    Edge cases:
        body_text may be empty for system entries.
    """

    id: str
    kind: ConversationKind
    body_text: str | None = None
    body_html: str | None = None
    from_email: str | None = None
    incoming: bool = False
    private: bool = False
    created_at: datetime | None = None
    raw: dict = {}


class TicketConversationsResponse(BaseModel):
    """Represent response for ticket conversation thread.

    Parameters:
        items: Ordered list of conversation entries.
        source: fresh or mock.
        error: True when Fresh returned an error and items may be incomplete.

    Returns:
        Ticket conversations API response.

    Edge cases:
        error=True with items=[] signals a graceful Fresh failure.
    """

    items: list[TicketConversation]
    source: str
    error: bool = False


class TicketRequester(BaseModel):
    """Represent a ticket requester.

    Parameters:
        name: Requester display name.
        email: Optional requester email.

    Returns:
        Requester value object.

    Edge cases:
        Fresh APIs differ by product; missing email is allowed.
    """

    name: str = "Unknown requester"
    email: str | None = None


class Ticket(BaseModel):
    """Represent normalized ticket data used by the app.

    Parameters:
        id: External Fresh ticket identifier.
        subject: Ticket subject.
        status: Ticket status.
        priority: Ticket priority.
        requester: Requester information.
        description: Optional textual description.
        raw: Original integration payload.

    Returns:
        Normalized ticket model.

    Edge cases:
        Unknown external fields remain available in raw.
    """

    id: str = Field(min_length=1)
    subject: str
    status: TicketStatus
    priority: TicketPriority
    requester: TicketRequester
    description: str | None = None
    url: str | None = None
    raw: dict[str, Any]
    sla: SlaHint | None = None
    overdue: bool = False


class TicketCacheDocument(BaseModel):
    """Represent a cached Fresh ticket document.

    Parameters:
        fresh_ticket_id: Fresh ticket identifier.
        subject: Ticket subject.
        status: Ticket status.
        priority: Ticket priority.
        requester: Requester information.
        raw: Original ticket payload.
        last_synced_at: Last successful sync time.

    Returns:
        Mongo-ready ticket cache payload.

    Edge cases:
        raw may include fields not represented by the normalized schema.
    """

    fresh_ticket_id: str
    subject: str
    status: TicketStatus
    priority: TicketPriority
    requester: dict[str, Any]
    raw: dict[str, Any]
    last_synced_at: datetime


class TicketListResponse(BaseModel):
    """Represent response for listing tickets.

    Parameters:
        items: Ticket collection.
        source: fresh or mock.
        cached: Whether tickets were written to cache.

    Returns:
        Ticket list API response.

    Edge cases:
        Empty ticket list is valid.
    """

    items: list[Ticket]
    source: str
    cached: bool


class TicketDetailResponse(BaseModel):
    """Represent response for a ticket detail request.

    Parameters:
        ticket: Ticket data.
        source: fresh, cache, or mock.

    Returns:
        Ticket detail API response.

    Edge cases:
        Mock ticket is returned when neither Fresh nor cache has data.
    """

    ticket: Ticket
    source: str
