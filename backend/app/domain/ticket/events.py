"""Ticket domain events."""

from dataclasses import dataclass

from app.domain.shared.base_event import DomainEvent
from app.domain.ticket.value_objects import TicketId


@dataclass(frozen=True, kw_only=True)
class TicketCreated(DomainEvent):
    """Published when a new ticket is detected in Freshservice.

    Parameters:
        ticket_id: External Freshservice ticket identifier.
        subject: Ticket subject.
        priority: Normalized priority.
        status: Normalized status.

    Returns:
        Domain event instance.
    """

    ticket_id: TicketId
    subject: str
    priority: str
    status: str


@dataclass(frozen=True, kw_only=True)
class TicketUpdated(DomainEvent):
    """Published when a ticket changes in Freshservice.

    Parameters:
        ticket_id: External Freshservice ticket identifier.
        changes: Dictionary of changed fields with new values.

    Returns:
        Domain event instance.
    """

    ticket_id: TicketId
    changes: dict[str, object]


@dataclass(frozen=True, kw_only=True)
class TicketWithoutTaskDetected(DomainEvent):
    """Published when an open ticket has no associated ClickUp task.

    Parameters:
        ticket_id: External Freshservice ticket identifier.
        subject: Ticket subject.
        reason: Why the ticket was flagged.

    Returns:
        Domain event instance.
    """

    ticket_id: TicketId
    subject: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class TicketUpdatedWithTaskLink(DomainEvent):
    """Published after a ticket is updated with a link to a ClickUp task.

    Parameters:
        ticket_id: External Freshservice ticket identifier.
        task_id: External ClickUp task identifier.
        note: Optional human-readable note added to the ticket.

    Returns:
        Domain event instance.
    """

    ticket_id: TicketId
    task_id: str
    note: str | None = None
