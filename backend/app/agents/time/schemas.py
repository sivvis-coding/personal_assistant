"""Schemas for the migrated time tracking agent.

These schemas used to live in app.assistant.schemas.time_agent. They were moved
here so the new event-driven TimeAgent does not depend on the legacy assistant
package. The legacy module re-exports them for backward compatibility.
"""

from datetime import date, datetime, time, timedelta
from typing import Any

from pydantic import BaseModel, Field

from app.tools.clickup_time_tracking import TimeEntryPreview


class TimeEntryParameters(BaseModel):
    """Represent time entry parameters extracted from a user message.

    Parameters:
        task_name: ClickUp task name to create.
        client_name: Optional client name for the ClickUp client field.
        description: Human-readable description of the work performed.
        duration_minutes: Requested duration in whole minutes.
        start_date: Local date for the time entry.
        start_time: Local start time for the time entry.

    Returns:
        Validated time entry parameters.

    Edge cases:
        Duration and start datetime may be inferred from user shorthand such as "3h" or "hoy".
    """

    task_name: str = ""
    client_name: str = ""
    description: str = ""
    duration_minutes: int = 0
    start_date: date | None = None
    start_time: time | None = None

    def is_complete(self) -> bool:
        """Return whether all required parameters are present.

        Parameters:
            None.

        Returns:
            True when the parameters are sufficient to build a time entry preview.

        Edge cases:
            Client is optional because the ClickUp list may not require it.
        """
        return bool(
            self.task_name
            and self.description
            and self.duration_minutes > 0
            and self.start_date is not None
            and self.start_time is not None
        )

    def missing_fields(self) -> list[str]:
        """Return human-readable labels for missing required parameters.

        Parameters:
            None.

        Returns:
            List of missing field labels in Spanish.

        Edge cases:
            Empty optional fields such as client_name are not reported as missing.
        """
        missing: list[str] = []
        if not self.task_name:
            missing.append("nombre de la tarea")
        if not self.description:
            missing.append("descripción del trabajo")
        if self.duration_minutes <= 0:
            missing.append("duración (ej. 2h, 30min)")
        if self.start_date is None:
            missing.append("fecha de inicio")
        if self.start_time is None:
            missing.append("hora de inicio")
        return missing

    def build_start_datetime(self) -> datetime:
        """Build a local start datetime from date and time components.

        Parameters:
            None.

        Returns:
            Combined local start datetime.

        Edge cases:
            Raises ValueError when date or time components are missing.
        """
        if self.start_date is None or self.start_time is None:
            raise ValueError("start_date and start_time are required to build a datetime")
        return datetime.combine(self.start_date, self.start_time)

    def build_end_datetime(self) -> datetime:
        """Build a local end datetime by adding the duration to the start.

        Parameters:
            None.

        Returns:
            Combined local end datetime.

        Edge cases:
            Raises ValueError when start datetime or duration is missing.
        """
        return self.build_start_datetime() + timedelta(minutes=self.duration_minutes)


class ExtractedActivity(BaseModel):
    """Represent one activity extracted by the LLM from a free-text daily narrative.

    Parameters:
        task_name: Short ClickUp task name for this activity.
        client_name: Client mentioned for this activity, if any.
        description: Human-readable description of the work performed.
        duration_minutes: Duration in whole minutes, 0 when not mentioned.
        start_date: Local date for the activity, None when not mentioned.
        start_time: Local start time for the activity, None when not mentioned.

    Returns:
        One structured activity candidate.

    Edge cases:
        Fields are left empty/zero/None rather than guessed when the narrative
        does not mention them, so the agent can ask for clarification instead
        of inventing data.
    """

    task_name: str = ""
    client_name: str = ""
    description: str = ""
    duration_minutes: int = 0
    start_date: date | None = None
    start_time: time | None = None


class DailyNarrativeExtraction(BaseModel):
    """Represent the LLM output for a free-text daily narrative.

    Parameters:
        activities: Activities segmented from the narrative, in the order mentioned.

    Returns:
        Structured extraction ready for per-activity resolution.

    Edge cases:
        A narrative describing a single activity still yields a one-item list.
    """

    activities: list[ExtractedActivity] = Field(default_factory=list)


class ActivityResolution(BaseModel):
    """Represent the resolved (or pending) state of a single daily activity.

    Parameters:
        success: Whether this activity is ready to be proposed as an action.
        answer: Human-readable note about this activity (missing fields, client ambiguity, or confirmation text).
        parameters: The time entry parameters for this activity.
        preview: Optional safe preview returned by the ClickUp time tracking tool.
        action_payload: Optional payload to store as a save_time_entry assistant action.
        needs_clarification: Whether the user must confirm or correct the client before this activity can proceed.
        candidate_clients: Candidate client names to disambiguate, when needs_clarification is True.

    Returns:
        Structured per-activity resolution.

    Edge cases:
        success is False and needs_clarification is False when required fields
        (task, description, duration, date/time) are missing — the user must
        resend a more complete narrative rather than being asked one field at a time.
    """

    success: bool
    answer: str
    parameters: TimeEntryParameters = Field(default_factory=TimeEntryParameters)
    preview: TimeEntryPreview | None = None
    action_payload: dict[str, Any] = Field(default_factory=dict)
    needs_clarification: bool = False
    candidate_clients: list[str] = Field(default_factory=list)


class TimeAgentResult(BaseModel):
    """Represent the output of the Time Agent for a daily narrative request.

    A single message may describe several activities (different clients/tasks),
    so the result carries one ActivityResolution per detected activity instead
    of a single flat outcome.

    Parameters:
        success: Whether at least one activity was resolved and is ready for approval.
        answer: Human-readable summary for the user (resolved activities + next pending question, if any).
        activities: Per-activity resolutions, in the order extracted from the message.
        list_id: Personal ClickUp list ID used to resolve these activities, so callers
            can reuse it when continuing a pending client confirmation.

    Returns:
        Structured time agent result.

    Edge cases:
        A single-activity message still produces a one-item activities list.
        list_id is empty when the request failed before a list could be resolved.
    """

    success: bool
    answer: str
    activities: list[ActivityResolution] = Field(default_factory=list)
    list_id: str = ""


class TimeEntryActionPayload(BaseModel):
    """Represent the payload stored for a save_time_entry assistant action.

    Parameters:
        task_name: ClickUp task name.
        description: Work description.
        start_datetime: ISO local start datetime string.
        end_datetime: ISO local end datetime string.
        client_name: Optional client name.

    Returns:
        Validated action payload.

    Edge cases:
        Datetime strings are stored without timezone because the tool assumes Europe/Madrid.
    """

    task_name: str
    description: str
    start_datetime: str
    end_datetime: str
    client_name: str = ""
