"""Assistant domain events."""

from dataclasses import dataclass

from app.domain.shared.base_event import DomainEvent
from app.domain.ticket.value_objects import TicketId


@dataclass(frozen=True, kw_only=True)
class AssistantMessageReceived(DomainEvent):
    """Published when the assistant receives a user message.

    Parameters:
        conversation_id: Conversation identifier.
        message: User message text.

    Returns:
        Domain event instance.
    """

    conversation_id: str
    message: str


@dataclass(frozen=True, kw_only=True)
class TicketTriageCompleted(DomainEvent):
    """Published when ticket triage finishes.

    Parameters:
        conversation_id: Conversation identifier.
        recommendations: List of ticket recommendations.

    Returns:
        Domain event instance.
    """

    conversation_id: str
    recommendations: list[dict]


@dataclass(frozen=True, kw_only=True)
class WorkPlanGenerated(DomainEvent):
    """Published when a prioritized work plan is generated.

    Parameters:
        conversation_id: Conversation identifier.
        work_plan: Prioritized work plan as a dictionary.

    Returns:
        Domain event instance.
    """

    conversation_id: str
    work_plan: dict


@dataclass(frozen=True, kw_only=True)
class TimeTrackingRequested(DomainEvent):
    """Published when a user requests time tracking.

    Parameters:
        conversation_id: Conversation identifier.
        message: User request text.
        confirmed_client: Optional client name already confirmed by the user.

    Returns:
        Domain event instance.
    """

    conversation_id: str
    message: str
    confirmed_client: str | None = None


@dataclass(frozen=True, kw_only=True)
class TimeTrackingPrepared(DomainEvent):
    """Published when a time entry preview is ready.

    Parameters:
        conversation_id: Conversation identifier.
        success: Whether the request was understood.
        answer: Human-readable response.
        preview: Optional preview dictionary.
        action_payload: Optional action payload dictionary.
        needs_clarification: Whether user clarification is needed.
        candidate_clients: Optional candidate client names.

    Returns:
        Domain event instance.
    """

    conversation_id: str
    success: bool
    answer: str
    preview: dict | None = None
    action_payload: dict | None = None
    needs_clarification: bool = False
    candidate_clients: list[str] | None = None
