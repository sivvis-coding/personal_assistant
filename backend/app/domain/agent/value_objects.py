"""Agent domain value objects."""

from dataclasses import dataclass

from app.domain.shared.base_value_object import ValueObject


@dataclass(frozen=True)
class AgentId(ValueObject):
    """Internal agent identifier.

    Parameters:
        value: Agent name or identifier.

    Returns:
        Validated agent identifier.

    Edge cases:
        Empty values are rejected.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("AgentId cannot be empty")


class AgentStatus(ValueObject):
    """Allowed agent execution status values."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
