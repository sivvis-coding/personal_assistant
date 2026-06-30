"""Shared context manager for multi-agent workflows."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from app.core.events.base import DomainEvent


@dataclass
class SharedContext:
    """Context shared between agents in a single workflow execution.

    Parameters:
        workflow_id: Unique workflow identifier.
        correlation_id: Correlation ID inherited from the initial event.
        data: Key-value store for inter-agent data.
        events_produced: Events produced during the workflow.

    Returns:
        Shared context instance.
    """

    workflow_id: UUID = field(default_factory=uuid4)
    correlation_id: UUID = field(default_factory=uuid4)
    data: dict[str, Any] = field(default_factory=dict)
    events_produced: list[DomainEvent] = field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:
        """Return a value from the shared context."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Store a value in the shared context."""
        self.data[key] = value


class ContextManager:
    """Factory and store for shared contexts.

    Phase 1 keeps contexts in memory. Future phases will persist them to
    MongoDB for audit and replay.
    """

    def __init__(self) -> None:
        """Initialize the context manager."""
        self._contexts: dict[UUID, SharedContext] = {}

    def create(self, initial_event: DomainEvent) -> SharedContext:
        """Create a new shared context for an event.

        Parameters:
            initial_event: Event that starts the workflow.

        Returns:
            New shared context.
        """
        context = SharedContext(correlation_id=initial_event.metadata.correlation_id)
        self._contexts[context.workflow_id] = context
        return context

    def get(self, workflow_id: UUID) -> SharedContext | None:
        """Return an existing context by workflow ID."""
        return self._contexts.get(workflow_id)

    def destroy(self, workflow_id: UUID) -> None:
        """Remove a context from memory."""
        self._contexts.pop(workflow_id, None)
