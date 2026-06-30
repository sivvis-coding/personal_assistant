"""Tests for the in-process event bus."""

import pytest

from app.core.events.base import DomainEvent
from app.domain.agent.events import TicketsReviewRequested
from app.domain.ticket.events import TicketWithoutTaskDetected
from app.domain.ticket.value_objects import TicketId
from app.infrastructure.events.in_process_bus import InProcessEventBus


class EventCollector:
    """Helper that records received events."""

    def __init__(self) -> None:
        self.received: list[DomainEvent] = []

    async def handle(self, event: DomainEvent) -> None:
        self.received.append(event)


@pytest.mark.asyncio
async def test_publish_dispatches_to_subscribed_handlers():
    """A published event should reach all subscribed handlers."""
    bus = InProcessEventBus()
    collector = EventCollector()

    bus.subscribe(TicketsReviewRequested, collector.handle)
    event = TicketsReviewRequested()

    await bus.publish(event)

    assert len(collector.received) == 1
    assert collector.received[0].event_id == event.event_id


@pytest.mark.asyncio
async def test_publish_ignores_unsubscribed_event_types():
    """Handlers subscribed to other event types should not be called."""
    bus = InProcessEventBus()
    collector = EventCollector()

    bus.subscribe(TicketWithoutTaskDetected, collector.handle)
    await bus.publish(TicketsReviewRequested())

    assert len(collector.received) == 0


@pytest.mark.asyncio
async def test_handler_failure_does_not_stop_other_handlers():
    """When one handler fails, others should still execute."""
    bus = InProcessEventBus()
    collector = EventCollector()

    async def failing_handler(_event: DomainEvent) -> None:
        raise RuntimeError("boom")

    bus.subscribe(TicketsReviewRequested, failing_handler)
    bus.subscribe(TicketsReviewRequested, collector.handle)

    await bus.publish(TicketsReviewRequested())

    assert len(collector.received) == 1


@pytest.mark.asyncio
async def test_publish_all_publishes_multiple_events():
    """publish_all should dispatch every event in the list."""
    bus = InProcessEventBus()
    collector = EventCollector()

    bus.subscribe(TicketsReviewRequested, collector.handle)
    bus.subscribe(TicketWithoutTaskDetected, collector.handle)

    await bus.publish_all([
        TicketsReviewRequested(),
        TicketWithoutTaskDetected(ticket_id=TicketId("42"), subject="Test", reason="No task"),
    ])

    assert len(collector.received) == 2
