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
        if self.start_date is None or self.start_time is None:
            missing.append("fecha y hora de inicio")
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


class TimeAgentResult(BaseModel):
    """Represent the output of the Time Agent for a single user request.

    Parameters:
        success: Whether the agent understood the request and produced a preview.
        answer: Human-readable response text for the user.
        parameters: Extracted time entry parameters.
        preview: Optional safe preview returned by the ClickUp time tracking tool.
        action_payload: Optional payload to store as an assistant action.
        needs_clarification: Whether the agent needs more user input before creating an action.
        proposed_client: Client name suggested for clarification.
        candidate_clients: Available client names to choose from.

    Returns:
        Structured time agent result.

    Edge cases:
        When success is False, preview and action_payload are empty and answer explains what is missing.
        When needs_clarification is True, the user must confirm or correct the proposed client.
    """

    success: bool
    answer: str
    parameters: TimeEntryParameters = Field(default_factory=TimeEntryParameters)
    preview: TimeEntryPreview | None = None
    action_payload: dict[str, Any] = Field(default_factory=dict)
    needs_clarification: bool = False
    proposed_client: str = ""
    candidate_clients: list[str] = Field(default_factory=list)


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
