"""Timesheet domain value objects."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.domain.shared.base_value_object import ValueObject


@dataclass(frozen=True)
class TimeRange(ValueObject):
    """A date/time range for a timesheet entry.

    Parameters:
        start: Start datetime.
        end: End datetime.

    Returns:
        Time range value object.

    Edge cases:
        End must be greater than or equal to start.
    """

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("TimeRange end must be greater than or equal to start")

    @property
    def duration_minutes(self) -> int:
        """Return the range duration in whole minutes."""
        return int((self.end - self.start).total_seconds() // 60)


@dataclass(frozen=True)
class TimeEntry(ValueObject):
    """A single timesheet entry.

    Parameters:
        task_id: Optional external task identifier.
        task_name: Human-readable task or ticket description.
        hours: Logged hours.
        date: Entry date.

    Returns:
        Timesheet entry value object.

    Edge cases:
        Hours must be non-negative.
    """

    task_id: str | None
    task_name: str
    hours: float
    date: date

    def __post_init__(self) -> None:
        if self.hours < 0:
            raise ValueError("TimeEntry hours cannot be negative")
