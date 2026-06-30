"""Base aggregate root primitive."""

from abc import ABC
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from app.domain.shared.base_event import DomainEvent


@dataclass(kw_only=True)
class AggregateRoot(ABC):
    """Base class for aggregate roots.

    Aggregate roots protect their invariants and expose domain events to
    notify the rest of the system about state changes.

    Parameters:
        id: Unique aggregate identifier.

    Returns:
        Aggregate root instance.

    Edge cases:
        Recorded events are not cleared automatically; callers must consume
        and clear them after persistence.
    """

    id: UUID = field(default_factory=uuid4)
    _events: list[DomainEvent] = field(default_factory=list, repr=False)

    def record_event(self, event: DomainEvent) -> None:
        """Record a domain event produced by this aggregate.

        Parameters:
            event: Domain event to record.

        Returns:
            None.
        """
        self._events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        """Return and clear recorded events.

        Parameters:
            None.

        Returns:
            List of recorded domain events.

        Edge cases:
            Calling this twice returns an empty list the second time.
        """
        events = self._events.copy()
        self._events.clear()
        return events
