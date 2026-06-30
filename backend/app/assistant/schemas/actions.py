from typing import Any, Literal

from pydantic import BaseModel, Field

AssistantActionType = Literal["prepare_clickup_task", "approve_clickup_task", "save_time_entry", "reply_freshservice_ticket"]
AssistantActionStatus = Literal["proposed", "approved", "rejected", "completed", "failed"]


class AssistantAction(BaseModel):
    """Represent an assistant-proposed action that may require approval.

    Parameters:
        id: Stored action identifier.
        action_type: Operation to execute.
        status: Current approval/execution state.
        title: Short display title.
        description: Human-readable explanation.
        ticket_id: Optional related Fresh ticket ID.
        payload: Action-specific payload.
        result: Optional execution result.
        requires_approval: Whether user approval is required before execution.

    Returns:
        Assistant action API contract.

    Edge cases:
        Result is present only after execution attempts.
    """

    id: str
    action_type: AssistantActionType
    status: AssistantActionStatus
    title: str
    description: str
    ticket_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    requires_approval: bool = True


class AssistantActionCreate(BaseModel):
    """Represent data required to persist a proposed assistant action.

    Parameters:
        action_type: Operation to execute.
        title: Short display title.
        description: Human-readable explanation.
        ticket_id: Optional related Fresh ticket ID.
        payload: Action-specific payload.
        requires_approval: Whether approval is required.

    Returns:
        Repository input for action creation.

    Edge cases:
        Payload must be serializable because it is stored in MongoDB.
    """

    action_type: AssistantActionType
    title: str
    description: str
    ticket_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = True
