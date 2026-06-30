import pytest

from app.agents.conversation.agent import ConversationAgent
from app.agents.conversation.schemas import ConversationResponse
from app.agents.time.agent import TimeAgent
from app.agents.time.extractor import TimeAgentParameterExtractor
from app.assistant.context_builder import AssistantContextBuilder
from app.assistant.conversation_service import AssistantConversationService
from app.assistant.schemas.actions import AssistantAction, AssistantActionCreate
from app.assistant.schemas.context import AssistantContext
from app.assistant.schemas.recommendations import PrioritizedWorkPlan
from app.schemas.clickup import WeekTimeResponse
from app.schemas.ticket import Ticket, TicketRequester
from app.tools.base import ToolInterface, ToolRegistry, ToolResult


class FakeConversationRepository:
    """In-memory conversation repository for tests.

    Parameters:
        None.

    Returns:
        Repository that records turns without MongoDB.

    Edge cases:
        IDs are deterministic counters to simplify assertions.
    """

    def __init__(self) -> None:
        """Initialize fake repository."""
        self._next_id = 1
        self.turns: list[dict] = []
        self._pending_state: dict | None = None

    async def create_conversation(self) -> str:
        """Return a deterministic conversation ID."""
        conversation_id = f"conv-{self._next_id}"
        self._next_id += 1
        return conversation_id

    async def append_turn(self, conversation_id: str, user_message: str, assistant_answer: str, metadata: dict) -> None:
        """Record a conversation turn in memory."""
        self.turns.append(
            {
                "conversation_id": conversation_id,
                "user_message": user_message,
                "assistant_answer": assistant_answer,
                "metadata": metadata,
            }
        )

    async def get_pending_state(self, conversation_id: str) -> dict | None:
        """Return the stored pending state."""
        return self._pending_state

    async def set_pending_state(self, conversation_id: str, state: dict | None) -> None:
        """Store or clear the pending state."""
        self._pending_state = state

    async def get_messages(self, conversation_id: str, limit: int = 10) -> list[dict]:
        """Return recorded turns up to the limit."""
        return self.turns[-limit:]


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


class FakeClickUpTimeTool(ToolInterface):
    """Fake ClickUp time tool returning deterministic previews."""

    name = "clickup_time"
    description = "Fake ClickUp time tool"
    parameters = []

    async def execute(self, **kwargs):
        from datetime import datetime

        if kwargs.get("operation") == "prepare":
            start = kwargs.get("start_datetime", "")
            end = kwargs.get("end_datetime", "")
            duration = 0
            if start and end:
                duration = int(
                    (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() // 60
                )
            return ToolResult.ok(
                data={
                    "task_name": kwargs.get("task_name"),
                    "description": kwargs.get("description"),
                    "start_datetime": start,
                    "end_datetime": end,
                    "client_name": kwargs.get("client_name", ""),
                    "duration_minutes": duration,
                }
            )
        return ToolResult.ok(data={"clients": []})


class FakeFreshserviceTool(ToolInterface):
    """Fake Freshservice tool for conversation service tests."""

    name = "freshservice"
    description = "Fake freshservice tool"
    parameters = []

    def __init__(self, response_data: dict) -> None:
        self._response_data = response_data

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult.ok(data=self._response_data)


class FakeClickUpTool(ToolInterface):
    """Fake ClickUp tool for conversation service tests."""

    name = "clickup"
    description = "Fake clickup tool"
    parameters = []

    def __init__(self, response_data: dict) -> None:
        self._response_data = response_data

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult.ok(data=self._response_data)


class FakeAssistantActionTool(ToolInterface):
    """In-memory assistant action tool for tests.

    Parameters:
        None.

    Returns:
        Tool that creates actions without MongoDB.

    Edge cases:
        Created actions always have status proposed.
    """

    name = "assistant_action"
    description = "Fake assistant action tool"
    parameters = []

    def __init__(self) -> None:
        """Initialize fake tool with no repository."""
        self._next_id = 1
        self.actions: list[AssistantAction] = []

    async def execute(self, **kwargs) -> ToolResult:
        """Create a fake action model with a deterministic ID."""
        fake_action = AssistantAction(
            id=f"action-{self._next_id}",
            action_type=kwargs.get("action_type", ""),
            status="proposed",
            title=kwargs.get("title", ""),
            description=kwargs.get("description", ""),
            ticket_id=kwargs.get("ticket_id"),
            payload=kwargs.get("payload", {}),
            result=None,
            requires_approval=True,
        )
        self._next_id += 1
        self.actions.append(fake_action)
        return ToolResult.ok(data=fake_action.model_dump())


class FakeContextBuilder:
    """Context builder that returns a minimal deterministic context."""

    async def build(self) -> AssistantContext:
        """Return a mock assistant context."""
        return AssistantContext(
            tickets=[
                Ticket(
                    id="1001",
                    subject="Test ticket",
                    status="open",
                    priority="medium",
                    requester=TicketRequester(name="Ada Lovelace", email="ada@example.com"),
                    description="Test description for context builder.",
                    raw={},
                )
            ],
            ticket_source="mock",
            week_time=WeekTimeResponse(source="mock", week_start="2026-06-22", week_end="2026-06-28", total_hours=0, entries=[]),
            existing_backlog_ticket_ids=[],
        )


class FakeConversationAgent(ConversationAgent):
    """Conversation agent that returns predictable non-time-tracking responses."""

    def __init__(self) -> None:
        """Initialize without an LLM provider."""
        pass

    async def respond(
        self,
        message: str,
        context: AssistantContext,
        tools: list[ToolInterface],
        message_history: list[dict] | None = None,
    ) -> ConversationResponse:
        """Return a generic conversation response."""
        return ConversationResponse(
            answer=f"Respuesta general para: {message}",
            recommendations=[],
            work_plan=PrioritizedWorkPlan(
                today_focus=[],
                next_actions=[],
                backlog_candidates=[],
                blocked_items=[],
                not_worth_actioning=[],
            ),
            proposed_actions=[],
        )


class FailingConversationAgent(ConversationAgent):
    """Conversation agent that always raises to test error handling."""

    def __init__(self) -> None:
        """Initialize without an LLM provider."""
        pass

    async def respond(
        self,
        message: str,
        context: AssistantContext,
        tools: list[ToolInterface],
        message_history: list[dict] | None = None,
    ) -> ConversationResponse:
        """Always raise an error."""
        raise RuntimeError("LLM unavailable")


@pytest.fixture
def conversation_service() -> AssistantConversationService:
    """Build a conversation service with in-memory test dependencies.

    Parameters:
        None.

    Returns:
        Service ready for unit testing.

    Edge cases:
        TimeAgent uses a fixed reference date to keep tests deterministic.
    """
    from datetime import date

    registry = ToolRegistry()
    registry.register(FakeFreshserviceTool({"tickets": []}))
    registry.register(FakeClickUpTool({"tasks": []}))

    return AssistantConversationService(
        conversation_repository=FakeConversationRepository(),
        assistant_action_tool=FakeAssistantActionTool(),
        context_builder=FakeContextBuilder(),
        conversation_agent=FakeConversationAgent(),
        time_agent=TimeAgent(
            memory_facade=FakeMemoryFacade(),
            clickup_time_tool=FakeClickUpTimeTool(),
            extractor=TimeAgentParameterExtractor(today=date(2026, 6, 29)),
        ),
        tool_registry=registry,
    )


@pytest.fixture
def failing_conversation_service() -> AssistantConversationService:
    """Build a conversation service whose LLM agent always fails."""
    from datetime import date

    registry = ToolRegistry()
    registry.register(FakeFreshserviceTool({"tickets": []}))
    registry.register(FakeClickUpTool({"tasks": []}))

    return AssistantConversationService(
        conversation_repository=FakeConversationRepository(),
        assistant_action_tool=FakeAssistantActionTool(),
        context_builder=FakeContextBuilder(),
        conversation_agent=FailingConversationAgent(),
        time_agent=TimeAgent(
            memory_facade=FakeMemoryFacade(),
            clickup_time_tool=FakeClickUpTimeTool(),
            extractor=TimeAgentParameterExtractor(today=date(2026, 6, 29)),
        ),
        tool_registry=registry,
    )


@pytest.mark.asyncio
async def test_should_route_time_tracking_request_to_time_agent(conversation_service: AssistantConversationService) -> None:
    """Verify time tracking messages create a save_time_entry action.

    Parameters:
        conversation_service: Test service fixture.

    Returns:
        None.

    Edge cases:
        Complete time tracking requests produce exactly one pending action.
    """
    # Arrange
    conversation_id = await conversation_service.create_conversation()

    # Act
    response = await conversation_service.handle_message(
        conversation_id,
        "Imputa 2h hoy a las 09:00 al cliente Acme por revisión del ticket 1001",
    )

    # Assert
    assert response.proposed_actions
    assert response.proposed_actions[0].action_type == "save_time_entry"
    assert response.proposed_actions[0].payload["client_name"] == "Acme"
    assert response.proposed_actions[0].payload["start_datetime"] == "2026-06-29T09:00:00"


@pytest.mark.asyncio
async def test_should_not_create_action_for_incomplete_time_tracking_request(conversation_service: AssistantConversationService) -> None:
    """Verify incomplete time tracking requests do not create pending actions.

    Parameters:
        conversation_service: Test service fixture.

    Returns:
        None.

    Edge cases:
        Missing start time triggers a clarification response.
    """
    # Arrange
    conversation_id = await conversation_service.create_conversation()

    # Act
    response = await conversation_service.handle_message(
        conversation_id,
        "Imputa 3h hoy al cliente Acme",
    )

    # Assert
    assert not response.proposed_actions
    assert "hora de inicio" in response.answer


@pytest.mark.asyncio
async def test_should_use_conversation_agent_for_non_time_tracking_messages(conversation_service: AssistantConversationService) -> None:
    """Verify non-time-tracking messages use the LLM conversation agent.

    Parameters:
        conversation_service: Test service fixture.

    Returns:
        None.

    Edge cases:
        General messages do not create time entry actions.
    """
    # Arrange
    conversation_id = await conversation_service.create_conversation()

    # Act
    response = await conversation_service.handle_message(conversation_id, "Hola, ¿qué tal?")

    # Assert
    assert response.answer == "Respuesta general para: Hola, ¿qué tal?"
    assert not response.proposed_actions


@pytest.mark.asyncio
async def test_should_return_friendly_error_when_llm_fails(
    failing_conversation_service: AssistantConversationService,
) -> None:
    """Verify LLM failures do not crash the endpoint.

    Parameters:
        failing_conversation_service: Test service fixture with a failing LLM agent.

    Returns:
        None.

    Edge cases:
        The user receives a friendly error message and no pending actions.
    """
    # Arrange
    conversation_id = await failing_conversation_service.create_conversation()

    # Act
    response = await failing_conversation_service.handle_message(conversation_id, "Hola")

    # Assert
    assert "no pude procesar" in response.answer
    assert not response.proposed_actions