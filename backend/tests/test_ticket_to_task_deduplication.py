"""Integration tests for ticket-to-task deduplication across write paths.

Verifies that the shared RelationType.TICKET_TO_TASK constant ensures both the
chat flow (TicketToClickUpTool.approve) and the agent/scheduler flow
(ClickUpAgent via TicketToClickUpTool) recognise links created by each other,
preventing duplicate ClickUp task creation.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.base import AgentContext
from app.agents.clickup.agent import ClickUpAgent
from app.agents.freshservice.agent import FreshserviceAgent
from app.agents.triage.agent import TicketTriageAgent
from app.core.memory.interface import AgentMemory, MemoryConfig, MemoryFacade
from app.domain.integration_link.value_objects import RelationType
from app.domain.ticket.events import TicketWithoutTaskDetected
from app.domain.ticket.value_objects import TicketId
from app.schemas.ai import UserStory
from app.schemas.clickup import ClickUpTaskResult
from app.schemas.ticket import Ticket, TicketRequester
from app.tools.base import ToolInterface, ToolResult
from app.tools.ticket_to_clickup.tool import TicketToClickUpTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_STORY = UserStory(
    title="Test story",
    description="Description",
    acceptance_criteria_in_gerkin="Given...",
    constraints="None",
    user_story_statement="As a user...",
    out_of_scope="None",
    requested_by="Requester",
    functional_description="Does something",
)


class FakeMemoryFacade(MemoryFacade):
    """Memory facade that returns a no-op AgentMemory."""

    def for_agent(self, agent_id: str) -> AgentMemory:
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
        subject="Demo ticket",
        status=status,
        priority="medium",
        requester=TicketRequester(name="Customer", email="customer@example.com"),
        description="Detailed problem description here.",
        raw={},
    )


def _build_ticket_to_clickup_tool(
    *,
    integration_link_repository: MagicMock,
    clickup_client: MagicMock | None = None,
) -> TicketToClickUpTool:
    """Build a TicketToClickUpTool with controlled collaborators."""
    ticket_service = MagicMock()
    ticket_service.get_ticket = AsyncMock(return_value=MagicMock(ticket=MagicMock()))

    ai_service = MagicMock()
    ai_service.ticket_to_user_story = AsyncMock(return_value=_USER_STORY)
    ai_service.model_name = "gpt-test"

    ai_draft_repository = MagicMock()
    ai_draft_repository.save_draft = AsyncMock(return_value="draft-1")

    workflow_run_repository = MagicMock()
    workflow_run_repository.start = AsyncMock(return_value="run-1")
    workflow_run_repository.finish_success = AsyncMock()

    return TicketToClickUpTool(
        ticket_service=ticket_service,
        ai_service=ai_service,
        ai_draft_repository=ai_draft_repository,
        integration_link_repository=integration_link_repository,
        workflow_run_repository=workflow_run_repository,
        clickup_client=clickup_client,
    )


class FakeTicketToClickUpTool(ToolInterface):
    """Fake TicketToClickUpTool that delegates to the real one for execute().

    Wraps the real tool so it can be retrieved by name from an AgentContext.
    """

    name = "ticket_to_clickup"
    description = "Fake ticket-to-ClickUp tool"
    parameters = []

    def __init__(self, real_tool: TicketToClickUpTool) -> None:
        self._real_tool = real_tool

    async def execute(self, **kwargs) -> ToolResult:
        return await self._real_tool.execute(**kwargs)


class FakeFreshserviceTool(ToolInterface):
    """Fake Freshservice tool returning deterministic tickets."""

    name = "freshservice"
    description = "Fake"
    parameters = []

    def __init__(self, tickets: list[Ticket]) -> None:
        self._tickets = tickets

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult.ok(data={"tickets": self._tickets, "source": "fake"})


class FakeMongoTool(ToolInterface):
    """Fake Mongo tool backed by an in-memory link store."""

    name = "mongo"
    description = "Fake"
    parameters = []

    def __init__(self, existing_link: dict | None = None) -> None:
        self._existing_link = existing_link

    async def execute(self, **kwargs) -> ToolResult:
        operation = kwargs.get("operation")
        if operation == "find_link":
            return ToolResult.ok(data=self._existing_link)
        if operation == "save_link":
            return ToolResult.ok(data={"link_id": "link-1"})
        return ToolResult.error(message="Unknown operation")


# ---------------------------------------------------------------------------
# 3a — constant value
# ---------------------------------------------------------------------------


def test_relation_type_constant_value() -> None:
    """RelationType.TICKET_TO_TASK must equal 'ticket_to_task'."""
    assert RelationType.TICKET_TO_TASK == "ticket_to_task"


# ---------------------------------------------------------------------------
# 3a — TicketToClickUpTool uses the shared constant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ticket_to_clickup_tool_queries_with_shared_constant() -> None:
    """TicketToClickUpTool.approve queries integration links using RelationType.TICKET_TO_TASK."""
    integration_link_repository = MagicMock()
    integration_link_repository.find_link = AsyncMock(return_value=None)
    integration_link_repository.save_link = AsyncMock(return_value="link-1")

    clickup_client = MagicMock()
    clickup_client.create_task_from_ticket = AsyncMock(
        return_value=ClickUpTaskResult(id="task-1", url="http://clickup/task-1", source="clickup")
    )

    tool = _build_ticket_to_clickup_tool(
        integration_link_repository=integration_link_repository,
        clickup_client=clickup_client,
    )

    await tool.execute(operation="approve", ticket_id="T-1", user_story=_USER_STORY.model_dump())

    integration_link_repository.find_link.assert_awaited_once_with(
        "fresh", "T-1", RelationType.TICKET_TO_TASK
    )


@pytest.mark.asyncio
async def test_ticket_to_clickup_tool_saves_with_shared_constant() -> None:
    """TicketToClickUpTool.approve persists integration links using RelationType.TICKET_TO_TASK."""
    from app.schemas.integration import IntegrationLinkDocument

    integration_link_repository = MagicMock()
    integration_link_repository.find_link = AsyncMock(return_value=None)
    integration_link_repository.save_link = AsyncMock(return_value="link-1")

    clickup_client = MagicMock()
    clickup_client.create_task_from_ticket = AsyncMock(
        return_value=ClickUpTaskResult(id="task-2", url="http://clickup/task-2", source="clickup")
    )

    tool = _build_ticket_to_clickup_tool(
        integration_link_repository=integration_link_repository,
        clickup_client=clickup_client,
    )

    await tool.execute(operation="approve", ticket_id="T-2", user_story=_USER_STORY.model_dump())

    call_args = integration_link_repository.save_link.call_args
    saved_doc: IntegrationLinkDocument = call_args[0][0]
    assert saved_doc.relation_type == RelationType.TICKET_TO_TASK


# ---------------------------------------------------------------------------
# 3c — ClickUpAgent routes through TicketToClickUpTool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clickup_agent_uses_ticket_to_clickup_tool() -> None:
    """ClickUpAgent must invoke TicketToClickUpTool instead of raw ClickUpTool."""
    integration_link_repository = MagicMock()
    integration_link_repository.find_link = AsyncMock(return_value=None)
    integration_link_repository.save_link = AsyncMock(return_value="link-1")

    clickup_client = MagicMock()
    clickup_client.create_task_from_ticket = AsyncMock(
        return_value=ClickUpTaskResult(id="task-3", url="http://clickup/task-3", source="clickup")
    )

    real_tool = _build_ticket_to_clickup_tool(
        integration_link_repository=integration_link_repository,
        clickup_client=clickup_client,
    )

    agent = ClickUpAgent(FakeMemoryFacade())
    context = AgentContext(tools=[FakeTicketToClickUpTool(real_tool)])
    event = TicketWithoutTaskDetected(
        ticket_id=TicketId("T-3"),
        subject="Need a task",
        reason="No ClickUp task linked",
        metadata={},
    )

    result = await agent.handle(event, context)

    assert result.summary is not None
    assert "task-3" in result.summary
    # The underlying client was called exactly once — not bypassed
    clickup_client.create_task_from_ticket.assert_awaited_once()


# ---------------------------------------------------------------------------
# Deduplication: chat path link recognised by agent/scheduler path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_skips_task_creation_when_chat_flow_already_created_link() -> None:
    """ClickUpAgent must not create a duplicate task when a link was already saved by the chat flow.

    The chat flow (TicketToClickUpTool) saves with relation_type=RelationType.TICKET_TO_TASK.
    The agent path also queries with RelationType.TICKET_TO_TASK.
    Using the shared constant ensures both paths match the same record.
    """
    existing_link = {
        "id": "link-existing",
        "target_id": "task-existing",
        "target_url": "http://clickup/task-existing",
    }

    integration_link_repository = MagicMock()
    integration_link_repository.find_link = AsyncMock(return_value=existing_link)
    integration_link_repository.save_link = AsyncMock(return_value="link-new")

    clickup_client = MagicMock()
    clickup_client.create_task_from_ticket = AsyncMock(
        return_value=ClickUpTaskResult(id="task-new", url="http://clickup/task-new", source="clickup")
    )

    real_tool = _build_ticket_to_clickup_tool(
        integration_link_repository=integration_link_repository,
        clickup_client=clickup_client,
    )

    agent = ClickUpAgent(FakeMemoryFacade())
    context = AgentContext(tools=[FakeTicketToClickUpTool(real_tool)])
    event = TicketWithoutTaskDetected(
        ticket_id=TicketId("T-4"),
        subject="Already has a task",
        reason="No ClickUp task linked",
        metadata={},
    )

    result = await agent.handle(event, context)

    # Task creation skipped; existing task re-used
    clickup_client.create_task_from_ticket.assert_not_called()
    integration_link_repository.save_link.assert_not_called()
    assert result.summary is not None
    assert "task-existing" in result.summary


# ---------------------------------------------------------------------------
# Deduplication: agent path link recognised by chat flow path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_flow_skips_task_creation_when_agent_already_created_link() -> None:
    """TicketToClickUpTool.approve must not create a duplicate when the agent path already saved a link.

    The agent path saves with relation_type=RelationType.TICKET_TO_TASK (via MongoTool default).
    The chat flow (TicketToClickUpTool) also queries with RelationType.TICKET_TO_TASK.
    Using the shared constant ensures both paths see the same record.
    """
    existing_link = {
        "id": "link-agent",
        "target_id": "task-agent",
        "target_url": "http://clickup/task-agent",
    }

    integration_link_repository = MagicMock()
    integration_link_repository.find_link = AsyncMock(return_value=existing_link)
    integration_link_repository.save_link = AsyncMock()

    clickup_client = MagicMock()
    clickup_client.create_task_from_ticket = AsyncMock()

    tool = _build_ticket_to_clickup_tool(
        integration_link_repository=integration_link_repository,
        clickup_client=clickup_client,
    )

    result = await tool.execute(operation="approve", ticket_id="T-5", user_story=_USER_STORY.model_dump())

    assert result.success is True
    assert result.data["clickup_task"]["source"] == "cache"
    assert result.data["clickup_task"]["id"] == "task-agent"
    clickup_client.create_task_from_ticket.assert_not_called()
    integration_link_repository.save_link.assert_not_called()


# ---------------------------------------------------------------------------
# Freshservice and Triage agents also use the shared constant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_freshservice_agent_queries_with_shared_constant() -> None:
    """FreshserviceAgent must query for links using RelationType.TICKET_TO_TASK."""
    from app.domain.agent.events import TicketsReviewRequested

    tickets = [_make_ticket("T-6")]
    fresh_tool = FakeFreshserviceTool(tickets)

    queried_relation_types: list[str] = []

    class RecordingMongoTool(ToolInterface):
        name = "mongo"
        description = "Recording mongo tool"
        parameters = []

        async def execute(self, **kwargs) -> ToolResult:
            if kwargs.get("operation") == "find_link":
                queried_relation_types.append(kwargs.get("relation_type", ""))
            return ToolResult.ok(data=None)

    agent = FreshserviceAgent(FakeMemoryFacade())
    context = AgentContext(tools=[fresh_tool, RecordingMongoTool()])

    await agent.handle(TicketsReviewRequested(), context)

    assert all(rt == RelationType.TICKET_TO_TASK for rt in queried_relation_types)


@pytest.mark.asyncio
async def test_triage_agent_queries_with_shared_constant() -> None:
    """TicketTriageAgent must query for links using RelationType.TICKET_TO_TASK."""
    from app.domain.assistant.events import AssistantMessageReceived

    tickets = [_make_ticket("T-7")]
    fresh_tool = FakeFreshserviceTool(tickets)

    queried_relation_types: list[str] = []

    class RecordingMongoTool(ToolInterface):
        name = "mongo"
        description = "Recording mongo tool"
        parameters = []

        async def execute(self, **kwargs) -> ToolResult:
            if kwargs.get("operation") == "find_link":
                queried_relation_types.append(kwargs.get("relation_type", ""))
            return ToolResult.ok(data=None)

    agent = TicketTriageAgent(FakeMemoryFacade())
    context = AgentContext(tools=[fresh_tool, RecordingMongoTool()])

    await agent.handle(AssistantMessageReceived(conversation_id="conv-1", message="review"), context)

    assert all(rt == RelationType.TICKET_TO_TASK for rt in queried_relation_types)
