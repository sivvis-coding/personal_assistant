"""Tests for the Freshservice agent."""

import pytest

from app.agents.freshservice.agent import FreshserviceAgent
from app.core.memory.interface import MemoryConfig, MemoryFacade
from app.domain.agent.events import TicketsReviewRequested
from app.domain.ticket.events import TicketWithoutTaskDetected
from app.domain.ticket.value_objects import TicketId
from app.schemas.ticket import Ticket, TicketRequester
from app.tools.base import ToolInterface, ToolResult


class FakeFreshserviceTool(ToolInterface):
    """Fake Freshservice tool returning deterministic tickets."""

    name = "freshservice"
    description = "Fake Freshservice tool"
    parameters = []

    def __init__(self, tickets: list[Ticket]) -> None:
        self._tickets = tickets

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult.ok(data={"tickets": self._tickets, "source": "fake"})


class FakeMongoTool(ToolInterface):
    """Fake Mongo tool with no links."""

    name = "mongo"
    description = "Fake Mongo tool"
    parameters = []

    def __init__(self, links: dict[str, dict] | None = None) -> None:
        self._links = links or {}

    async def execute(self, **kwargs) -> ToolResult:
        operation = kwargs.get("operation")
        if operation == "find_link":
            source_id = kwargs.get("source_id")
            return ToolResult.ok(data=self._links.get(source_id))
        if operation == "save_link":
            return ToolResult.ok(data={"link_id": "link-1"})
        return ToolResult.error(message="Unknown operation")


class FakeMemoryFacade(MemoryFacade):
    """Memory facade that returns a no-op AgentMemory."""

    def for_agent(self, agent_id: str):
        from app.core.memory.interface import AgentMemory

        return AgentMemory(
            agent_id=agent_id,
            config=MemoryConfig(),
            short_term=None,
            long_term=None,
            semantic=None,
            user_prefs=None,
        )


def _make_ticket(ticket_id: str, status: str = "open") -> Ticket:
    return Ticket(
        id=ticket_id,
        subject="Test ticket",
        status=status,
        priority="medium",
        requester=TicketRequester(name="Customer", email="customer@example.com"),
        description="Description",
        raw={},
    )


@pytest.mark.asyncio
async def test_detects_unlinked_open_tickets():
    """The agent should emit TicketWithoutTaskDetected for open unlinked tickets."""
    tickets = [_make_ticket("1"), _make_ticket("2", status="closed")]
    agent = FreshserviceAgent(FakeMemoryFacade())
    from app.agents.base import AgentContext

    context = AgentContext(tools=[FakeFreshserviceTool(tickets), FakeMongoTool()])
    result = await agent.handle(TicketsReviewRequested(), context)

    events = [e for e in result.events if isinstance(e, TicketWithoutTaskDetected)]
    assert len(events) == 1
    assert events[0].ticket_id == TicketId("1")


@pytest.mark.asyncio
async def test_skips_tickets_with_existing_link():
    """The agent should not emit events for tickets already linked to a task."""
    tickets = [_make_ticket("1")]
    mongo_tool = FakeMongoTool(links={"1": {"target_id": "clickup-1"}})
    agent = FreshserviceAgent(FakeMemoryFacade())
    from app.agents.base import AgentContext

    context = AgentContext(tools=[FakeFreshserviceTool(tickets), mongo_tool])
    result = await agent.handle(TicketsReviewRequested(), context)

    events = [e for e in result.events if isinstance(e, TicketWithoutTaskDetected)]
    assert len(events) == 0
