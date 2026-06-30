"""Event subscription registry."""

from collections.abc import Callable
from typing import Any

from app.core.events.base import DomainEvent
from app.core.events.bus import EventBus

EventHandler = Callable[[DomainEvent], Any]


class EventRegistry:
    """Declarative registry for event subscriptions.

    Registrations are collected during construction and applied to an event
    bus during bootstrap. This keeps subscription wiring explicit and easy to
    review.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._subscriptions: list[tuple[type[DomainEvent], EventHandler]] = []

    def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: EventHandler,
    ) -> None:
        """Register a handler for an event type.

        Parameters:
            event_type: Domain event class.
            handler: Event handler callable.

        Returns:
            None.
        """
        self._subscriptions.append((event_type, handler))

    def apply(self, event_bus: EventBus) -> None:
        """Apply all registered subscriptions to an event bus.

        Parameters:
            event_bus: Event bus to subscribe handlers on.

        Returns:
            None.
        """
        for event_type, handler in self._subscriptions:
            event_bus.subscribe(event_type, handler)
