"""Base domain event primitive."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.core.time import utc_now


@dataclass(frozen=True, kw_only=True)
class EventMetadata:
    """Metadata attached to every domain event.

    Parameters:
        correlation_id: Groups all events produced within the same workflow.
        causation_id: The event that directly caused this event, if any.
        source: Human-readable source of the event (agent name, scheduler, etc.).
        extra: Additional domain-agnostic metadata.

    Returns:
        Event metadata instance.

    Edge cases:
        Correlation ID is generated when not provided so every event can be
        traced back to a workflow execution.
    """

    correlation_id: UUID = field(default_factory=uuid4)
    causation_id: UUID | None = None
    source: str = "unknown"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Base class for all domain events.

    Domain events represent facts that happened in the past. They are
    immutable and used to communicate between agents without coupling them.

    Parameters:
        event_id: Unique event identifier.
        occurred_on: UTC timestamp when the event occurred.
        metadata: Event tracing metadata.

    Returns:
        Domain event instance.

    Edge cases:
        Subclasses must be frozen dataclasses so events remain immutable.
    """

    event_id: UUID = field(default_factory=uuid4)
    occurred_on: datetime = field(default_factory=utc_now)
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def with_causation(self, cause: "DomainEvent", source: str | None = None) -> "DomainEvent":
        """Create a new event that references its cause.

        Parameters:
            cause: Event that caused this event.
            source: Optional source override.

        Returns:
            New event with copied correlation and causation metadata.

        Edge cases:
            Preserves the original correlation_id so the full chain can be
            reconstructed.
        """
        metadata = EventMetadata(
            correlation_id=cause.metadata.correlation_id,
            causation_id=cause.event_id,
            source=source or self.metadata.source,
            extra=dict(self.metadata.extra),
        )
        return self.__class__(
            event_id=self.event_id,
            occurred_on=self.occurred_on,
            metadata=metadata,
        )
