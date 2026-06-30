"""Task domain events."""

from dataclasses import dataclass

from app.domain.shared.base_event import DomainEvent
from app.domain.task.value_objects import TaskId
from app.domain.ticket.value_objects import TicketId


@dataclass(frozen=True, kw_only=True)
class ClickUpStatusSyncRequested(DomainEvent):
    """Published by the scheduler to trigger ClickUp-to-Freshservice status sync.

    When the scheduler fires this event the ClickUpStatusSyncAgent queries all
    ticket_to_task integration links, compares current ClickUp task statuses
    against the last-known values, and posts a private note to Freshservice for
    any link where the status changed.

    Returns:
        Domain event instance.
    """

    pass


@dataclass(frozen=True, kw_only=True)
class TaskCreatedFromTicket(DomainEvent):
    """Published when a ClickUp task is created from a Freshservice ticket.

    Parameters:
        task_id: External ClickUp task identifier.
        ticket_id: Source Freshservice ticket identifier.
        title: Task title.
        url: ClickUp task URL.

    Returns:
        Domain event instance.
    """

    task_id: TaskId
    ticket_id: TicketId
    title: str
    url: str


@dataclass(frozen=True, kw_only=True)
class TaskUpdated(DomainEvent):
    """Published when a ClickUp task changes.

    Parameters:
        task_id: External ClickUp task identifier.
        status: Normalized status value.
        changes: Dictionary of changed fields with new values.

    Returns:
        Domain event instance.
    """

    task_id: TaskId
    status: str
    changes: dict[str, object]


@dataclass(frozen=True, kw_only=True)
class TaskBlocked(DomainEvent):
    """Published when a task is detected as blocked.

    Parameters:
        task_id: External ClickUp task identifier.
        reason: Human-readable reason for the blockage.

    Returns:
        Domain event instance.
    """

    task_id: TaskId
    reason: str
