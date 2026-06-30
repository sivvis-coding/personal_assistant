"""Task domain value objects."""

from dataclasses import dataclass

from app.domain.shared.base_value_object import ValueObject


@dataclass(frozen=True)
class TaskId(ValueObject):
    """External ClickUp task identifier.

    Parameters:
        value: Raw task identifier string.

    Returns:
        Validated task identifier.

    Edge cases:
        Empty values are rejected because external identifiers must be stable.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("TaskId cannot be empty")


class TaskStatus:
    """Allowed task status values."""

    TODO = "to do"
    IN_PROGRESS = "in progress"
    REVIEW = "review"
    BLOCKED = "blocked"
    DONE = "done"
    UNKNOWN = "unknown"
