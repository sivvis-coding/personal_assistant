"""Agent and scheduler domain events."""

from dataclasses import dataclass
from typing import Any

from app.domain.agent.value_objects import AgentId
from app.domain.shared.base_event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class AgentStarted(DomainEvent):
    """Published when an agent starts processing an event.

    Parameters:
        agent_id: Agent identifier.
        event_type: Type of event being handled.

    Returns:
        Domain event instance.
    """

    agent_id: AgentId
    event_type: str


@dataclass(frozen=True, kw_only=True)
class AgentCompleted(DomainEvent):
    """Published when an agent finishes successfully.

    Parameters:
        agent_id: Agent identifier.
        event_type: Type of event handled.
        result_summary: Human-readable summary of the result.

    Returns:
        Domain event instance.
    """

    agent_id: AgentId
    event_type: str
    result_summary: str


@dataclass(frozen=True, kw_only=True)
class AgentFailed(DomainEvent):
    """Published when an agent fails.

    Parameters:
        agent_id: Agent identifier.
        event_type: Type of event being handled.
        error: Error message.

    Returns:
        Domain event instance.
    """

    agent_id: AgentId
    event_type: str
    error: str


@dataclass(frozen=True, kw_only=True)
class MorningSummaryRequested(DomainEvent):
    """Published by the scheduler to request the morning summary."""

    pass


@dataclass(frozen=True, kw_only=True)
class MorningSummaryGenerated(DomainEvent):
    """Published when the morning summary is ready.

    Parameters:
        summary: Human-readable summary text.
        plan: List of planned actions for the day.

    Returns:
        Domain event instance.
    """

    summary: str
    plan: list[str]


@dataclass(frozen=True, kw_only=True)
class DailyReviewRequested(DomainEvent):
    """Published by the scheduler to request the daily review."""

    pass


@dataclass(frozen=True, kw_only=True)
class TicketsReviewRequested(DomainEvent):
    """Published by the scheduler to request a ticket review."""

    pass


@dataclass(frozen=True, kw_only=True)
class TasksReviewRequested(DomainEvent):
    """Published by the scheduler to request a task review."""

    pass


@dataclass(frozen=True, kw_only=True)
class TimesheetReviewRequested(DomainEvent):
    """Published by the scheduler to request a timesheet review."""

    pass
