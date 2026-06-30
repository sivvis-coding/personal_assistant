"""Event bus interface."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from app.core.events.base import DomainEvent

EventHandler = Callable[[DomainEvent], Any]


class EventBus(ABC):
    """Abstract event bus.

    The event bus is the only mechanism through which agents and application
    layers communicate. It keeps producers and consumers decoupled.
    """

    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Publish a single event to all subscribers.

        Parameters:
            event: Domain event to publish.

        Returns:
            None.
        """

    @abstractmethod
    async def publish_all(self, events: list[DomainEvent]) -> None:
        """Publish multiple events sequentially.

        Parameters:
            events: List of domain events to publish.

        Returns:
            None.
        """

    @abstractmethod
    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        """Subscribe a handler to a specific event type.

        Parameters:
            event_type: Domain event class to subscribe to.
            handler: Async or sync callable that receives the event.

        Returns:
            None.
        """

    @abstractmethod
    def add_middleware(self, middleware: "EventMiddleware") -> None:
        """Add middleware to the event pipeline.

        Parameters:
            middleware: Middleware instance to register.

        Returns:
            None.
        """
