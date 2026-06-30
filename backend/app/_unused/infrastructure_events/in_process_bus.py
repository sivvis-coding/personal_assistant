"""In-process event bus implementation."""

import asyncio
import inspect
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from app.core.events.base import DomainEvent
from app.core.events.bus import EventBus, EventHandler
from app.core.events.middleware import EventMiddleware
from app.core.logging.logger import logger


class InProcessEventBus(EventBus):
    """Synchronous/asynchronous in-memory event bus.

    This implementation dispatches events to handlers in the same process.
    It is the simplest event bus and is sufficient for a single-instance
    personal assistant. It can be replaced by a message broker later without
    changing consumers.

    Parameters:
        max_handler_depth: Maximum event causation depth to prevent cycles.

    Returns:
        In-process event bus instance.

    Edge cases:
        Handler exceptions are logged and do not stop other handlers.
        Event cycles are detected using the causation chain length.
    """

    def __init__(self, max_handler_depth: int = 5) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)
        self._middleware: list[EventMiddleware] = []
        self._max_handler_depth = max_handler_depth

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        """Subscribe a handler to an event type."""
        self._handlers[event_type].append(handler)

    def add_middleware(self, middleware: EventMiddleware) -> None:
        """Add middleware to the event pipeline."""
        self._middleware.append(middleware)

    async def publish(self, event: DomainEvent) -> None:
        """Publish a single event."""
        if self._is_cycle(event):
            logger.warning(
                "Event cycle detected",
                extra={
                    "event_type": type(event).__name__,
                    "event_id": str(event.event_id),
                    "correlation_id": str(event.metadata.correlation_id),
                },
            )
            return

        handlers = list(self._handlers.get(type(event), []))
        for middleware in self._middleware:
            handlers = await middleware.process(event, handlers)

        for handler in handlers:
            await self._run_handler(handler, event)

    async def publish_all(self, events: list[DomainEvent]) -> None:
        """Publish multiple events sequentially."""
        for event in events:
            await self.publish(event)

    async def _run_handler(self, handler: EventHandler, event: DomainEvent) -> None:
        """Execute a single handler and log failures."""
        try:
            if inspect.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Event handler failed",
                extra={
                    "event_type": type(event).__name__,
                    "event_id": str(event.event_id),
                    "handler": getattr(handler, "__name__", repr(handler)),
                    "error": str(exc),
                },
            )

    def _is_cycle(self, event: DomainEvent) -> bool:
        """Detect potential event cycles by causation depth."""
        depth = 0
        current: DomainEvent | None = event
        while current is not None and current.metadata.causation_id is not None:
            depth += 1
            if depth >= self._max_handler_depth:
                return True
            current = None
        return False
