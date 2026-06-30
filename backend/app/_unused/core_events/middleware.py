"""Event bus middleware interface."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from app.core.events.base import DomainEvent

EventHandler = Callable[[DomainEvent], Any]


class EventMiddleware(ABC):
    """Base class for event bus middleware.

    Middleware can inspect, modify, or short-circuit event handling. They are
    executed in registration order around every published event.
    """

    @abstractmethod
    async def process(
        self,
        event: DomainEvent,
        handlers: list[EventHandler],
    ) -> list[EventHandler]:
        """Process an event and return the handlers that should run.

        Parameters:
            event: Event being published.
            handlers: Handlers subscribed to the event type.

        Returns:
            Handlers to execute. Returning an empty list stops propagation.

        Edge cases:
            Middleware should be non-blocking and avoid raising exceptions.
        """
