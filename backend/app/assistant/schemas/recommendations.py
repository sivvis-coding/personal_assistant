from typing import Literal

from pydantic import BaseModel, Field

TicketRecommendationCategory = Literal["action_now", "backlog_candidate", "needs_more_info", "ignore_or_monitor", "already_in_backlog"]


class TicketRecommendation(BaseModel):
    """Represent the assistant recommendation for one ticket.

    Parameters:
        ticket_id: Fresh ticket identifier.
        subject: Ticket subject for display.
        category: Recommended operational bucket.
        confidence: Rule confidence from 0 to 1.
        rationale: Human-readable reason behind the recommendation.
        suggested_next_action: Concrete next action for the user.
        missing_information: Information needed before acting.

    Returns:
        Ticket triage recommendation.

    Edge cases:
        Low confidence recommendations should be treated as advisory, not executable.
    """

    ticket_id: str
    subject: str
    category: TicketRecommendationCategory
    confidence: float = Field(ge=0, le=1)
    rationale: str
    suggested_next_action: str
    missing_information: list[str] = Field(default_factory=list)


class PrioritizedWorkPlan(BaseModel):
    """Represent a prioritized work plan generated from recommendations.

    Parameters:
        today_focus: Highest-value recommendations to review first.
        next_actions: Actionable recommendations after today's focus.
        backlog_candidates: Tickets that can be converted into backlog tasks.
        blocked_items: Tickets that need more information.
        not_worth_actioning: Tickets that should be monitored or ignored for now.

    Returns:
        Work plan grouped by operational intent.

    Edge cases:
        Empty groups are valid when no matching tickets exist.
    """

    today_focus: list[TicketRecommendation]
    next_actions: list[TicketRecommendation]
    backlog_candidates: list[TicketRecommendation]
    blocked_items: list[TicketRecommendation]
    not_worth_actioning: list[TicketRecommendation]
