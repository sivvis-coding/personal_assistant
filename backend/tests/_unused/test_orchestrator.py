"""Tests for the orchestrator."""

import pytest

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.events.base import DomainEvent
from app.core.memory.interface import MemoryConfig, MemoryFacade
from app.domain.agent.events import TicketsReviewRequested
from app.domain.ticket.events import TicketWithoutTaskDetected
from app.domain.ticket.value_objects import TicketId
from app.infrastructure.events.in_process_bus import InProcessEventBus
from app.infrastructure.memory.short_term_store import InMemoryShortTermMemory
from app.orchestrator.context_manager import ContextManager
from app.orchestrator.orchestrator import Orchestrator
from app.orchestrator.router import EventRouter
from app.tools.base import ToolInterface


class SpyAgent(BaseAgent):
    """Agent that records handled events and produces a fixed event."""

    agent_id = "spy"

    def __init__(self) -> None:
        super().__init__(
            agent_id="spy",
            memory_config=MemoryConfig(),
            memory_facade=FakeMemoryFacade(),
        )
        self.handled: list[DomainEvent] = []

    async def _handle(self, event: DomainEvent, context: AgentContext) -> AgentResult:
        self.handled.append(event)
        return AgentResult(
            events=[
                TicketWithoutTaskDetected(
                    ticket_id=TicketId("99"),
                    subject="Produced",
                    reason="test",
                    metadata=event.metadata,
                )
            ],
            summary="handled",
        )


class FakeMemoryFacade(MemoryFacade):
    """Memory facade returning a no-op AgentMemory."""

    def for_agent(self, agent_id: str):
        from app.core.memory.interface import AgentMemory

        return AgentMemory(
            agent_id=agent_id,
            config=MemoryConfig(),
            short_term=InMemoryShortTermMemory(),
            long_term=None,
            semantic=None,
            user_prefs=None,
        )


class NoOpTool(ToolInterface):
    """No-op tool for testing."""

    name = "noop"
    description = "Does nothing"
    parameters = []

    async def execute(self, **kwargs) -> "ToolResult":
        from app.tools.base import ToolResult

        return ToolResult.ok()


@pytest.mark.asyncio
async def test_orchestrator_routes_event_to_agent_and_publishes_result():
    """The orchestrator should route events, execute agents, and publish produced events."""
    bus = InProcessEventBus()
    router = EventRouter()
    spy = SpyAgent()
    router.register(TicketsReviewRequested, spy)

    received: list[DomainEvent] = []
    bus.subscribe(TicketWithoutTaskDetected, lambda e: received.append(e))

    orchestrator = Orchestrator(
        event_bus=bus,
        router=router,
        context_manager=ContextManager(),
        tools=[NoOpTool()],
        memory_facade=FakeMemoryFacade(),
    )

    results = await orchestrator.start_workflow(TicketsReviewRequested())

    assert len(results) == 1
    assert len(spy.handled) == 1
    assert len(received) == 1
    assert received[0].ticket_id == TicketId("99")


@pytest.mark.asyncio
async def test_orchestrator_ignores_events_with_no_agent():
    """The orchestrator should return empty results when no agent is registered."""
    bus = InProcessEventBus()
    router = EventRouter()

    orchestrator = Orchestrator(
        event_bus=bus,
        router=router,
        context_manager=ContextManager(),
        tools=[],
        memory_facade=FakeMemoryFacade(),
    )

    results = await orchestrator.start_workflow(TicketsReviewRequested())

    assert results == []
