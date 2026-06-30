"""Legacy API schemas for the time tracking assistant.

The domain schemas (TimeEntryParameters, TimeAgentResult, TimeEntryActionPayload)
now live in app.agents.time.schemas. They are re-exported here so existing tests
and legacy code keep working during the migration.
"""

from datetime import date, datetime, time, timedelta
from typing import Any

from pydantic import BaseModel, Field

from app.agents.time.schemas import (
    TimeAgentResult as TimeAgentResult,
    TimeEntryActionPayload as TimeEntryActionPayload,
    TimeEntryParameters as TimeEntryParameters,
)
from app.assistant.schemas.actions import AssistantAction
from app.tools.clickup_time_tracking import TimeEntryPreview


class TimeTrackingWeekSummary(BaseModel):
    """Represent a lightweight week time summary for assistant answers.

    Parameters:
        total_hours: Total hours logged for the current week.
        days_count: Number of days with time entries.

    Returns:
        Summary suitable for natural language responses.

    Edge cases:
        Mock sources are preserved so the assistant can disclose low confidence.
    """

    total_hours: float
    days_count: int = 0


class TimeTrackingRequest(BaseModel):
    """Represent a user request sent to the time tracking assistant endpoint.

    Parameters:
        message: Natural language time tracking request.

    Returns:
        Validated request payload.

    Edge cases:
        Empty messages are rejected by validation.
    """

    message: str = Field(min_length=1)


class TimeTrackingProcessResponse(BaseModel):
    """Represent the response after processing a time tracking request.

    Parameters:
        success: Whether the request was understood and a preview was generated.
        answer: Human-readable assistant answer.
        preview: Optional time entry preview for user review.
        proposed_action: Optional assistant action created for HITL approval.

    Returns:
        Complete time tracking turn response.

    Edge cases:
        proposed_action is present only when success is True and a pending action was stored.
    """

    success: bool
    answer: str
    preview: TimeEntryPreview | None = None
    proposed_action: AssistantAction | None = None
