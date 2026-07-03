"""Schemas for the conversation agent."""

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

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
        Non-dict recommendations (e.g. plain strings from the LLM) are silently dropped.
        work_plan dicts missing required fields are coerced to None instead of raising.
    """

    answer: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    recommendations: list[TicketRecommendation] = Field(default_factory=list)
    work_plan: PrioritizedWorkPlan | None = None
    proposed_actions: list[AssistantActionCreate] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: str = ""
    memory_updates: list[dict[str, Any]] = Field(default_factory=list)
    next_suggestions: list[str] = Field(default_factory=list)

    @field_validator("recommendations", mode="before")
    @classmethod
    def drop_invalid_recommendations(cls, v: Any) -> list[Any]:
        if not isinstance(v, list):
            return []
        return [item for item in v if isinstance(item, dict)]

    @field_validator("work_plan", mode="before")
    @classmethod
    def coerce_invalid_work_plan(cls, v: Any) -> Any:
        if v is None:
            return None
        if not isinstance(v, dict):
            return None
        required = {"today_focus", "next_actions", "backlog_candidates", "blocked_items", "not_worth_actioning"}
        if not required.issubset(v.keys()):
            return None
        return v

    @field_validator("next_suggestions", mode="before")
    @classmethod
    def sanitize_next_suggestions(cls, v: Any) -> list[Any]:
        if not isinstance(v, list):
            return []
        result = []
        for item in v:
            if not isinstance(item, str):
                continue
            result.append(item[:80])
        return result
