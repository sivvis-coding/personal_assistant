"""Ticket domain value objects."""

from dataclasses import dataclass

from app.domain.shared.base_value_object import ValueObject


@dataclass(frozen=True)
class TicketId(ValueObject):
    """External Freshservice ticket identifier.

    Parameters:
        value: Raw ticket identifier string.

    Returns:
        Validated ticket identifier.

    Edge cases:
        Empty values are rejected because external identifiers must be stable.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("TicketId cannot be empty")


class Status:
    """Allowed ticket status values.

    These are normalized strings used across the system so agents do not
    depend on Freshservice-specific status codes.
    """

    OPEN = "open"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class Priority:
    """Allowed ticket priority values."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    UNKNOWN = "unknown"
