"""Timesheet domain events."""

from dataclasses import dataclass
from datetime import date

from app.domain.shared.base_event import DomainEvent
from app.domain.timesheet.value_objects import TimeEntry


@dataclass(frozen=True, kw_only=True)
class TimesheetMissing(DomainEvent):
    """Published when hours are missing for a given date.

    Parameters:
        missing_date: Date with missing hours.
        missing_hours: Number of hours still to log.
        suggestions: Human-readable suggestions for imputation.

    Returns:
        Domain event instance.
    """

    missing_date: date
    missing_hours: float
    suggestions: list[str]


@dataclass(frozen=True, kw_only=True)
class TimesheetCompleted(DomainEvent):
    """Published when a timesheet is completed.

    Parameters:
        completed_date: Date of the completed timesheet.
        entries: Entries that make up the timesheet.

    Returns:
        Domain event instance.
    """

    completed_date: date
    entries: list[TimeEntry]
