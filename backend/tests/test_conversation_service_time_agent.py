from datetime import date, time

import pytest

from app.agents.conversation.agent import ConversationAgent
from app.agents.conversation.schemas import ConversationResponse
from app.agents.time.agent import TimeAgent
from app.agents.time.schemas import TimeEntryParameters
from app.assistant.context_builder import AssistantContextBuilder
from app.assistant.conversation_service import AssistantConversationService
from app.assistant.schemas.actions import AssistantAction, AssistantActionCreate
from app.assistant.schemas.context import AssistantContext
from app.assistant.schemas.recommendations import PrioritizedWorkPlan
from app.schemas.clickup import WeekTimeResponse
from app.schemas.settings import AppSettings
from app.schemas.ticket import Ticket, TicketRequester
from app.tools.base import ToolInterface, ToolRegistry, ToolResult

TODAY = date(2026, 6, 29)


class ScriptedNarrativeExtractor:
    """Test double returning pre-scripted activities for known test messages.

    Stands in for the LLM-based DailyNarrativeExtractor so conversation
    service tests stay deterministic without calling an LLM.
    """

    async def extract(
        self,
        message: str,
        today: date,
        known_clients: list[str] | None = None,
        assume_today_if_missing: bool = False,
    ) -> list[TimeEntryParameters]:
        if "3h en soporte" in message:
            # No date mentioned at all — mirrors the real prompt's
            # assume_today_if_missing behavior for a day-scoped conversation.
            return [
                TimeEntryParameters(
                    task_name="Soporte",
                    client_name="Acme",
                    description="Soporte general",
                    duration_minutes=180,
                    start_date=today if assume_today_if_missing else None,
                    start_time=time(9, 0),
                )
            ]
        if "refinamiento tech para dev" in message:
            # Client is already known from the narrative; duration/time are not
            # mentioned yet — stays incomplete until a completion round fills them in.
            return [
                TimeEntryParameters(
                    task_name="Refinamiento tech",
                    client_name="Dev",
                    description="Refinamiento tech para dev",
                    duration_minutes=0,
                    start_date=None,
                    start_time=None,
                )
            ]
        if "1001" in message:
            return [
                TimeEntryParameters(
                    task_name="Revisión del ticket 1001",
                    client_name="Acme",
                    description="Revisión del ticket 1001",
                    duration_minutes=120,
                    start_date=TODAY,
                    start_time=time(9, 0),
                )
            ]
        if "cliente Acem" in message:
            return [
                TimeEntryParameters(
                    task_name="Soporte para Acem",
                    client_name="Acem",  # typo, ambiguous against the real "Acme" client
                    description="Soporte para Acem",
                    duration_minutes=120,
                    start_date=TODAY,
                    start_time=time(9, 0),
                )
            ]
        if "cliente Acme" in message:
            return [
                TimeEntryParameters(
                    task_name="Trabajo para Acme",
                    client_name="Acme",
                    description="Trabajo para Acme",
                    duration_minutes=180,
                    start_date=TODAY,
                    start_time=None,
                )
            ]
        return []

    async def complete(
        self,
        pending_activities: list[TimeEntryParameters],
        message: str,
        today: date,
        known_clients: list[str] | None = None,
        assume_today_if_missing: bool = False,
    ) -> list[TimeEntryParameters]:
        if "9 a 10:30" in message:
            return [
                TimeEntryParameters(
                    task_name=activity.task_name,
                    client_name=activity.client_name,
                    description=activity.description,
                    duration_minutes=90,
                    start_date=TODAY,
                    start_time=time(9, 0),
                )
                for activity in pending_activities
            ]
        return pending_activities


class FakeSettingsService:
    """Settings service stub returning a fixed personal ClickUp list id."""

    async def get_settings(self) -> AppSettings:
        return AppSettings(clickup_personal_list_id="list-1")


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
        self._target_date: date | None = None

    async def create_conversation(self, target_date: date | None = None) -> str:
        """Return a deterministic conversation ID."""
        conversation_id = f"conv-{self._next_id}"
        self._next_id += 1
        self._target_date = target_date
        return conversation_id

    async def get_target_date(self, conversation_id: str) -> date | None:
        """Return the day this conversation is scoped to, if any."""
        return self._target_date

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

    def __init__(self, clients: list[str] | None = None) -> None:
        self._clients = clients or []

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
        return ToolResult.ok(data={"clients": self._clients})


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
        TimeAgent uses a scripted narrative extractor to keep tests deterministic.
    """
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
            narrative_extractor=ScriptedNarrativeExtractor(),
            settings_service=FakeSettingsService(),
            clickup_time_tool=FakeClickUpTimeTool(),
        ),
        tool_registry=registry,
    )


@pytest.fixture
def failing_conversation_service() -> AssistantConversationService:
    """Build a conversation service whose LLM agent always fails."""
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
            narrative_extractor=ScriptedNarrativeExtractor(),
            settings_service=FakeSettingsService(),
            clickup_time_tool=FakeClickUpTimeTool(),
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
async def test_should_not_route_narrative_without_keyword_to_time_agent(conversation_service: AssistantConversationService) -> None:
    """Verify a free-form narrative with NO time keyword goes to the conversation
    agent, not the TimeAgent — routing is explicit-only, so ordinary chat is never
    silently reinterpreted as logged hours.

    Parameters:
        conversation_service: Test service fixture.

    Returns:
        None.

    Edge cases:
        The message must not contain any of TimeAgent.TIME_TRACKING_KEYWORDS.
    """
    # Arrange
    conversation_id = await conversation_service.create_conversation()

    # Act
    message = "El otro día dediqué 2h a las 09:00 al cliente Acme revisando el ticket 1001"
    response = await conversation_service.handle_message(conversation_id, message)

    # Assert: handled by the conversation agent, no time entry proposed
    assert response.answer == f"Respuesta general para: {message}"
    assert not response.proposed_actions


@pytest.mark.asyncio
async def test_should_default_date_to_conversation_target_date(conversation_service: AssistantConversationService) -> None:
    """Verify a message with no date at all defaults to the conversation's target_date.

    This is the "click a day in the calendar to log hours for it" flow: the
    conversation is scoped to one day, so the user only needs to describe the
    work and hours — not the date.

    Parameters:
        conversation_service: Test service fixture.

    Returns:
        None.
    """
    # Arrange
    conversation_id = await conversation_service.create_conversation(target_date=date(2026, 6, 1))

    # Act (explicit keyword routes to the TimeAgent; extractor keys on "3h en soporte")
    response = await conversation_service.handle_message(conversation_id, "Imputa 3h en soporte al cliente Acme")

    # Assert
    assert response.proposed_actions
    assert response.proposed_actions[0].payload["start_datetime"] == "2026-06-01T09:00:00"


@pytest.mark.asyncio
async def test_should_leave_date_missing_without_target_date(conversation_service: AssistantConversationService) -> None:
    """Verify the same message without a scoped conversation still asks for the date.

    Regression guard: assume_today_if_missing must only kick in when the
    conversation was explicitly scoped to a day, not for regular chat.

    Parameters:
        conversation_service: Test service fixture.

    Returns:
        None.
    """
    # Arrange
    conversation_id = await conversation_service.create_conversation()

    # Act
    response = await conversation_service.handle_message(conversation_id, "Imputa 3h en soporte al cliente Acme")

    # Assert
    assert not response.proposed_actions
    assert "fecha de inicio" in response.answer


@pytest.fixture
def conversation_service_with_known_clients() -> AssistantConversationService:
    """Build a conversation service where the ClickUp client field has real options.

    Used to exercise the ambiguous-client confirmation queue end to end.
    """
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
            narrative_extractor=ScriptedNarrativeExtractor(),
            settings_service=FakeSettingsService(),
            clickup_time_tool=FakeClickUpTimeTool(clients=["Acme"]),
        ),
        tool_registry=registry,
    )


@pytest.mark.asyncio
async def test_should_resolve_pending_client_confirmation_on_next_message(
    conversation_service_with_known_clients: AssistantConversationService,
) -> None:
    """Verify an ambiguous client is queued, and the very next message (with no
    keyword at all) is treated as the confirmation reply rather than a new request.

    This is a regression test: pending state is stored with type
    "client_confirmation_queue" and must be read back with the same type.

    Parameters:
        conversation_service_with_known_clients: Test service fixture with a real client list.

    Returns:
        None.
    """
    # Arrange
    conversation_id = await conversation_service_with_known_clients.create_conversation()

    # Act: narrative with a typo'd client, ambiguous against the real "Acme"
    first_response = await conversation_service_with_known_clients.handle_message(
        conversation_id,
        "Imputa 2h hoy a las 09:00 al cliente Acem por soporte",
    )

    # Assert: no action yet, waiting for client confirmation
    assert not first_response.proposed_actions
    assert "Acme" in first_response.answer

    # Act: reply with the confirmed client name
    second_response = await conversation_service_with_known_clients.handle_message(conversation_id, "Acme")

    # Assert: the queued activity is now resolved into a pending action
    assert second_response.proposed_actions
    assert second_response.proposed_actions[0].action_type == "save_time_entry"
    assert second_response.proposed_actions[0].payload["client_name"] == "Acme"


@pytest.mark.asyncio
async def test_should_let_user_cancel_pending_client_confirmation_and_change_topic(
    conversation_service_with_known_clients: AssistantConversationService,
) -> None:
    """Verify a cancellation reply clears the pending client queue and the message
    is routed normally instead of being consumed as a client name."""
    # Arrange
    conversation_id = await conversation_service_with_known_clients.create_conversation()
    await conversation_service_with_known_clients.handle_message(
        conversation_id,
        "Imputa 2h hoy a las 09:00 al cliente Acem por soporte",
    )

    # Act: back out and change topic in the same message
    response = await conversation_service_with_known_clients.handle_message(
        conversation_id, "olvídalo, ¿qué tal?"
    )

    # Assert: routed to the conversation agent, pending state cleared (no time action)
    assert response.answer == "Respuesta general para: olvídalo, ¿qué tal?"
    assert not response.proposed_actions


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
async def test_should_use_conversation_agent_for_task_creation_requests(
    conversation_service: AssistantConversationService,
) -> None:
    """Verify a request to create a new US/task is never hijacked by the TimeAgent.

    Parameters:
        conversation_service: Test service fixture.

    Returns:
        None.

    Edge cases:
        Regression test: "quiero crear una US" has no time-tracking keyword, and
        must not fall through to the TimeAgent's speculative narrative extractor
        (which would otherwise ask for a duration/start time).
    """
    # Arrange
    conversation_id = await conversation_service.create_conversation()

    # Act
    response = await conversation_service.handle_message(conversation_id, "Quiero crear una US")

    # Assert
    assert response.answer == "Respuesta general para: Quiero crear una US"
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


@pytest.mark.asyncio
async def test_should_merge_followup_reply_into_incomplete_narrative(
    conversation_service: AssistantConversationService,
) -> None:
    """Verify a follow-up reply providing missing duration/time completes the
    original activity instead of being treated as an unrelated new message,
    and that the client already extracted in the first turn is preserved.

    Regression coverage for the "narrative_completion" pending state: without
    it, a reply like "duró de 9 a 10:30" would either be misrouted to the
    general conversation agent or lose the client on re-extraction.

    Parameters:
        conversation_service: Test service fixture.

    Returns:
        None.
    """
    # Arrange
    conversation_id = await conversation_service.create_conversation()

    # Act: narrative with no duration/time — stays incomplete, client already known
    first_response = await conversation_service.handle_message(
        conversation_id,
        "Imputa el 1 de junio: estuve haciendo refinamiento tech para dev",
    )

    # Assert: no action yet, asked for missing data
    assert not first_response.proposed_actions
    assert "necesito más datos" in first_response.answer

    # Act: follow-up reply with just the missing detail
    second_response = await conversation_service.handle_message(conversation_id, "duró de 9 a 10:30")

    # Assert: the same activity is now resolved into a pending action, client preserved
    assert second_response.proposed_actions
    assert second_response.proposed_actions[0].action_type == "save_time_entry"
    assert second_response.proposed_actions[0].payload["client_name"] == "Dev"
    assert second_response.proposed_actions[0].payload["start_datetime"] == "2026-06-29T09:00:00"
    assert second_response.proposed_actions[0].payload["end_datetime"] == "2026-06-29T10:30:00"