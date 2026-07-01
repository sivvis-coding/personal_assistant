"""Schemas for the conversation agent."""

from typing import Any

from pydantic import BaseModel, Field

from app.assistant.schemas.actions import AssistantActionCreate
from app.assistant.schemas.recommendations import PrioritizedWorkPlan, TicketRecommendation


class ToolCall(BaseModel):
    """Represent a tool call requested by the conversation agent.

    Parameters:
        tool: Name of the tool to execute.
        operation: Operation to perform on the tool.
        parameters: Additional operation-specific parameters.

    Returns:
        Validated tool call.

    Edge cases:
        Unknown tools or operations will fail during execution.
    """

    tool: str
    operation: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ConversationResponse(BaseModel):
    """Structured response from the conversation agent.

    Parameters:
        answer: Human-readable assistant answer in Spanish.
        tool_calls: Optional list of tools to execute before answering.
        recommendations: Optional ticket recommendations displayed to the user.
        work_plan: Optional prioritized work plan.
        proposed_actions: Pending actions proposed for human approval.
        needs_clarification: Whether the assistant needs more user input.
        clarification_question: Question to ask the user when clarification is needed.
        memory_updates: Key/value pairs to persist as user preferences after this turn.

    Returns:
        Validated conversation response.

    Edge cases:
        When needs_clarification is True, proposed_actions and tool_calls should be empty.
        memory_updates entries without a "key" field are silently ignored.
    """

    answer: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    recommendations: list[TicketRecommendation] = Field(default_factory=list)
    work_plan: PrioritizedWorkPlan | None = None
    proposed_actions: list[AssistantActionCreate] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: str = ""
    memory_updates: list[dict[str, Any]] = Field(default_factory=list)
