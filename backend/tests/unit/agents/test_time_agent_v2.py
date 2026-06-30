"""Tests for the migrated time agent."""

import pytest

from app.agents.base import AgentContext
from app.agents.time.agent import TimeAgent
from app.agents.time.extractor import TimeAgentParameterExtractor
from app.domain.assistant.events import TimeTrackingRequested
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


def test_is_time_tracking_request_detects_keywords():
    """The agent recognizes time-tracking intent from keywords."""
    assert TimeAgent.is_time_tracking_request("imputa 2h hoy")
    assert not TimeAgent.is_time_tracking_request("hola")


@pytest.mark.asyncio
async def test_process_extracts_complete_request():
    """The agent extracts parameters and builds a success result."""
    from datetime import date

    extractor = TimeAgentParameterExtractor(today=date(2024, 6, 15))
    agent = TimeAgent(
        memory_facade=FakeMemoryFacade(),
        clickup_time_tool=FakeClickUpTimeTool(),
        extractor=extractor,
    )

    result = await agent.process("imputa 3h hoy a las 9h por revisión de tickets")

    assert result.success is True
    assert result.preview["duration_minutes"] == 180
    assert result.action_payload["task_name"] != ""


@pytest.mark.asyncio
async def test_process_asks_for_missing_fields():
    """Incomplete requests trigger a clarification response."""
    agent = TimeAgent(memory_facade=FakeMemoryFacade(), clickup_time_tool=FakeClickUpTimeTool())

    result = await agent.process("imputa tiempo")

    assert result.success is False
    assert result.needs_clarification is True
    assert "Falta" in result.answer


@pytest.mark.asyncio
async def test_handle_emits_time_tracking_prepared_event():
    """The event handler emits TimeTrackingPrepared."""
    from datetime import date

    extractor = TimeAgentParameterExtractor(today=date(2024, 6, 15))
    agent = TimeAgent(
        memory_facade=FakeMemoryFacade(),
        clickup_time_tool=FakeClickUpTimeTool(),
        extractor=extractor,
    )
    context = AgentContext(tools=[FakeClickUpTimeTool()])

    result = await agent.handle(
        TimeTrackingRequested(conversation_id="conv-1", message="imputa 3h hoy a las 9h por revisión"),
        context,
    )

    assert len(result.events) == 1
    assert result.events[0].conversation_id == "conv-1"
    assert result.events[0].success is True
