"""Tests for the migrated ticket triage agent."""

import pytest

from app.agents.base import AgentContext
from app.agents.triage.agent import TicketTriageAgent
from app.domain.assistant.events import AssistantMessageReceived
from app.schemas.ticket import Ticket, TicketRequester


class FakeMemoryFacade:
    """Memory facade returning a no-op AgentMemory."""

    def for_agent(self, agent_id: str):
        from app.core.memory.interface import AgentMemory, MemoryConfig

        return AgentMemory(
            agent_id=agent_id,
            config=MemoryConfig(),
            short_term=None,
            long_term=None,
            semantic=None,
            user_prefs=None,
        )


def _make_ticket(ticket_id: str, status: str = "open", priority: str = "medium", description: str = "Detailed problem description here.") -> Ticket:
    return Ticket(
        id=ticket_id,
        subject="Test ticket",
        status=status,
        priority=priority,
        requester=TicketRequester(name="Customer", email="customer@example.com"),
        description=description,
        raw={},
    )


def test_analyze_marks_high_priority_as_action_now():
    """High-priority tickets with enough context are classified as action_now."""
    agent = TicketTriageAgent(FakeMemoryFacade())
    tickets = [_make_ticket("1", priority="high")]

    recommendations = agent.analyze(tickets, set())

    assert len(recommendations) == 1
    assert recommendations[0].category == "action_now"


def test_analyze_marks_linked_ticket_as_already_in_backlog():
    """Tickets already linked to ClickUp are classified as already_in_backlog."""
    agent = TicketTriageAgent(FakeMemoryFacade())
    tickets = [_make_ticket("1")]

    recommendations = agent.analyze(tickets, {"1"})

    assert recommendations[0].category == "already_in_backlog"


def test_analyze_marks_resolved_ticket_as_ignore():
    """Resolved tickets are classified as ignore_or_monitor."""
    agent = TicketTriageAgent(FakeMemoryFacade())
    tickets = [_make_ticket("1", status="resolved")]

    recommendations = agent.analyze(tickets, set())

    assert recommendations[0].category == "ignore_or_monitor"


def test_analyze_marks_short_description_as_needs_more_info():
    """Tickets with very short descriptions need more info."""
    agent = TicketTriageAgent(FakeMemoryFacade())
    tickets = [_make_ticket("1", description="Short.")]

    recommendations = agent.analyze(tickets, set())

    assert recommendations[0].category == "needs_more_info"


class FakeFreshserviceTool:
    """Fake Freshservice tool returning deterministic tickets."""

    name = "freshservice"
    description = "Fake Freshservice tool"
    parameters = []

    def __init__(self, tickets: list[Ticket]) -> None:
        self._tickets = tickets

    async def execute(self, **kwargs):
        from app.tools.base import ToolResult

        return ToolResult.ok(data={"tickets": self._tickets, "source": "fake"})


class FakeMongoTool:
    """Fake Mongo tool with no links."""

    name = "mongo"
    description = "Fake Mongo tool"
    parameters = []

    async def execute(self, **kwargs):
        from app.tools.base import ToolResult

        operation = kwargs.get("operation")
        if operation == "find_link":
            return ToolResult.ok(data=None)
        return ToolResult.error(message="Unknown")


@pytest.mark.asyncio
async def test_handle_emits_triage_completed_event():
    """The event handler emits TicketTriageCompleted with recommendations."""
    agent = TicketTriageAgent(FakeMemoryFacade())
    tickets = [_make_ticket("1", priority="high")]
    context = AgentContext(
        tools=[
            FakeFreshserviceTool(tickets),
            FakeMongoTool(),
        ]
    )

    result = await agent.handle(AssistantMessageReceived(conversation_id="conv-1", message="review tickets"), context)

    assert len(result.events) == 1
    assert result.events[0].conversation_id == "conv-1"
    assert len(result.events[0].recommendations) == 1

