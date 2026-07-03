"""Tests for the migrated time agent."""

from datetime import date, time

import pytest

from app.agents.base import AgentContext
from app.agents.time.agent import TimeAgent
from app.agents.time.schemas import TimeEntryParameters
from app.domain.assistant.events import TimeTrackingRequested
from app.schemas.settings import AppSettings
from app.tools.base import ToolInterface, ToolResult


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
    """Fake ClickUp time tool returning deterministic clients and previews."""

    name = "clickup_time"
    description = "Fake ClickUp time tool"
    parameters = []

    def __init__(self, clients: list[str] | None = None) -> None:
        self._clients = clients or []

    async def execute(self, **kwargs) -> ToolResult:
        operation = kwargs.get("operation")
        if operation == "get_clients":
            return ToolResult.ok(data={"clients": self._clients})
        if operation == "prepare":
            return ToolResult.ok(
                data={
                    "task_name": kwargs.get("task_name"),
                    "description": kwargs.get("description"),
                    "start_datetime": kwargs.get("start_datetime"),
                    "end_datetime": kwargs.get("end_datetime"),
                    "client_name": kwargs.get("client_name", ""),
                    "duration_minutes": 180,
                }
            )
        return ToolResult.error(message="Unknown")


class FakeNarrativeExtractor:
    """Deterministic stand-in for DailyNarrativeExtractor in tests."""

    def __init__(self, activities: list[TimeEntryParameters]) -> None:
        self._activities = activities

    async def extract(self, message: str, today: date) -> list[TimeEntryParameters]:
        return self._activities


class FakeSettingsService:
    """Settings service stub returning a fixed personal ClickUp list id."""

    def __init__(self, list_id: str = "list-1") -> None:
        self._list_id = list_id

    async def get_settings(self) -> AppSettings:
        return AppSettings(clickup_personal_list_id=self._list_id)


def test_is_time_tracking_request_detects_keywords():
    """The agent recognizes time-tracking intent from keywords."""
    assert TimeAgent.is_time_tracking_request("imputa 2h hoy")
    assert not TimeAgent.is_time_tracking_request("hola")


@pytest.mark.asyncio
async def test_process_extracts_complete_request():
    """The agent resolves an extracted activity and builds a success result."""
    activity = TimeEntryParameters(
        task_name="Revisión de tickets",
        client_name="",
        description="Revisión de tickets",
        duration_minutes=180,
        start_date=date(2024, 6, 15),
        start_time=time(9, 0),
    )
    agent = TimeAgent(
        memory_facade=FakeMemoryFacade(),
        narrative_extractor=FakeNarrativeExtractor([activity]),
        settings_service=FakeSettingsService(),
        clickup_time_tool=FakeClickUpTimeTool(),
    )

    result = await agent.process("imputa 3h hoy a las 9h por revisión de tickets")

    assert result.success is True
    resolved = result.activities[0]
    assert resolved.preview["duration_minutes"] == 180
    assert resolved.action_payload["task_name"] != ""


@pytest.mark.asyncio
async def test_process_asks_for_missing_fields():
    """Incomplete activities are reported without guessing missing data."""
    agent = TimeAgent(
        memory_facade=FakeMemoryFacade(),
        narrative_extractor=FakeNarrativeExtractor([TimeEntryParameters()]),
        settings_service=FakeSettingsService(),
        clickup_time_tool=FakeClickUpTimeTool(),
    )

    result = await agent.process("imputa tiempo")

    assert result.success is False
    assert result.activities[0].needs_clarification is False
    assert "necesito más datos" in result.activities[0].answer


@pytest.mark.asyncio
async def test_process_returns_no_activities_when_narrative_has_no_work():
    """A narrative with no identifiable work yields no activities."""
    agent = TimeAgent(
        memory_facade=FakeMemoryFacade(),
        narrative_extractor=FakeNarrativeExtractor([]),
        settings_service=FakeSettingsService(),
        clickup_time_tool=FakeClickUpTimeTool(),
    )

    result = await agent.process("hola, ¿qué tal?")

    assert result.success is False
    assert result.activities == []


@pytest.mark.asyncio
async def test_handle_emits_time_tracking_prepared_event():
    """The event handler emits TimeTrackingPrepared."""
    activity = TimeEntryParameters(
        task_name="Revisión",
        client_name="",
        description="Revisión",
        duration_minutes=180,
        start_date=date(2024, 6, 15),
        start_time=time(9, 0),
    )
    agent = TimeAgent(
        memory_facade=FakeMemoryFacade(),
        narrative_extractor=FakeNarrativeExtractor([activity]),
        settings_service=FakeSettingsService(),
        clickup_time_tool=FakeClickUpTimeTool(),
    )
    context = AgentContext(tools=[FakeClickUpTimeTool()])

    result = await agent.handle(
        TimeTrackingRequested(conversation_id="conv-1", message="imputa 3h hoy a las 9h por revisión"),
        context,
    )

    assert len(result.events) == 1
    assert result.events[0].conversation_id == "conv-1"
    assert result.events[0].success is True
