from datetime import date, datetime

from pydantic import BaseModel, Field

from app.assistant.schemas.actions import AssistantAction
from app.assistant.schemas.recommendations import PrioritizedWorkPlan, TicketRecommendation


class AssistantConversationCreateRequest(BaseModel):
    """Represent the optional body for creating a new conversation.

    Parameters:
        target_date: Optional day this conversation is scoped to (e.g. started
            from a calendar click), so time-tracking messages default their
            date to it instead of requiring it to be spelled out every time.

    Returns:
        Validated conversation creation input.

    Edge cases:
        Omitted entirely, a conversation is not scoped to any particular day.
    """

    target_date: date | None = None


class AssistantMessageRequest(BaseModel):
    """Represent a user message sent to the assistant.

    Parameters:
        message: Natural language user request.

    Returns:
        Validated assistant message input.

    Edge cases:
        Empty messages are rejected by validation.
    """

    message: str = Field(min_length=1)


class AssistantConversationCreateResponse(BaseModel):
    """Represent a newly created assistant conversation.

    Parameters:
        conversation_id: Stored conversation identifier.

    Returns:
        Conversation creation response.

    Edge cases:
        Conversation initially contains no messages.
    """

    conversation_id: str


class AssistantMessageResponse(BaseModel):
    """Represent assistant response for one user message.

    Parameters:
        conversation_id: Related conversation identifier.
        answer: Human-readable assistant answer.
        recommendations: Ticket recommendations considered for the answer.
        work_plan: Prioritized grouped plan.
        proposed_actions: Actions that require user review or approval.
        needs_clarification: Whether the assistant needs more information.
        clarification_question: Question the assistant wants to ask.

    Returns:
        Complete assistant turn response.

    Edge cases:
        Proposed actions are suggestions until explicitly approved.
    """

    conversation_id: str
    answer: str
    recommendations: list[TicketRecommendation]
    work_plan: PrioritizedWorkPlan
    proposed_actions: list[AssistantAction]
    needs_clarification: bool = False
    clarification_question: str = ""
    next_suggestions: list[str] = Field(default_factory=list)


class ConversationMessage(BaseModel):
    """Represent a single turn in a conversation.

    Parameters:
        user_message: User input text.
        assistant_answer: Assistant response text.
        created_at: When the turn was created.

    Returns:
        A conversation turn.
    """

    user_message: str
    assistant_answer: str
    created_at: datetime


class ConversationSummaryResponse(BaseModel):
    """Represent a conversation summary for the history list.

    Parameters:
        id: Conversation identifier.
        title: Extracted from first user message.
        message_count: Total number of turns.
        updated_at: Last activity timestamp.

    Returns:
        Conversation summary for listing.
    """

    id: str
    title: str
    message_count: int
    updated_at: datetime


class ConversationDetailResponse(BaseModel):
    """Represent a complete conversation with all messages.

    Parameters:
        id: Conversation identifier.
        title: Extracted from first user message.
        messages: All conversation turns.
        created_at: When the conversation was created.
        updated_at: Last activity timestamp.
        target_date: Day this conversation is scoped to, if started from a calendar click.

    Returns:
        Complete conversation for detail view.
    """

    id: str
    title: str
    messages: list[ConversationMessage]
    created_at: datetime
    updated_at: datetime
    target_date: date | None = None
