"""Schemas for the planner agent."""

from pydantic import BaseModel, Field


class MorningSummaryResponse(BaseModel):
    """Structured response from the LLM for a morning summary.

    Parameters:
        summary: Human-readable workload summary.
        plan: Prioritized list of daily action items.

    Returns:
        Validated morning summary response.

    Edge cases:
        Empty plan is allowed but discouraged by the prompt.
    """

    summary: str = Field(..., max_length=500)
    plan: list[str] = Field(default_factory=list)
