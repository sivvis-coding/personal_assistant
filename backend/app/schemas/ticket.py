from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
    status: str
    priority: str
    requester: TicketRequester
    description: str | None = None
    raw: dict[str, Any]


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
    status: str
    priority: str
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
