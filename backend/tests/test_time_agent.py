"""Tests for the migrated time agent and related safety/execution flows.

These tests used to import the legacy app.assistant.agents.time_agent module.
They now exercise the migrated app.agents.time.agent implementation.
"""

from datetime import date, time
from unittest.mock import MagicMock

import pytest

from app.agents.time.agent import TimeAgent
from app.agents.time.extractor import TimeAgentParameterExtractor
from app.assistant.action_executor import AssistantActionExecutor
from app.assistant.safety_policy import AssistantSafetyPolicy
from app.assistant.schemas.actions import AssistantAction
from app.core.memory.interface import AgentMemory, MemoryConfig
from app.tools.base import ToolInterface, ToolResult
from app.tools.clickup_time.tool import ClickUpTimeTool


class FakeMemoryFacade:
    """Memory facade returning a no-op AgentMemory."""

    def for_agent(self, agent_id: str) -> AgentMemory:
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

    async def execute(self, **kwargs) -> ToolResult:
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


@pytest.fixture
def fixed_extractor() -> TimeAgentParameterExtractor:
    """Provide an extractor pinned to a known reference date."""
    return TimeAgentParameterExtractor(today=date(2026, 6, 29))


def test_should_extract_three_hour_duration() -> None:
    """Verify hour shorthand is parsed into minutes."""
    extractor = TimeAgentParameterExtractor(today=date(2026, 6, 29))

    parameters = extractor.extract("Imputa 3h hoy al cliente Acme por revisión de ticket")

    assert parameters.duration_minutes == 180


def test_should_extract_mixed_hour_and_minute_duration() -> None:
    """Verify combined hour and minute patterns are summed."""
    extractor = TimeAgentParameterExtractor(today=date(2026, 6, 29))

    parameters = extractor.extract("Registra 2h30m ayer para revisión")

    assert parameters.duration_minutes == 150


def test_should_extract_client_name() -> None:
    """Verify client name is extracted after common Spanish prefixes."""
    extractor = TimeAgentParameterExtractor(today=date(2026, 6, 29))

    parameters = extractor.extract("Imputa 1h hoy al cliente Globex por soporte")

    assert parameters.client_name == "Globex"


def test_should_resolve_relative_dates(fixed_extractor: TimeAgentParameterExtractor) -> None:
    """Verify relative date words resolve against the reference date."""
    today_params = fixed_extractor.extract("Imputa 1h hoy")
    yesterday_params = fixed_extractor.extract("Imputa 1h ayer")

    assert today_params.start_date == date(2026, 6, 29)
    assert yesterday_params.start_date == date(2026, 6, 28)


def test_should_extract_start_time() -> None:
    """Verify clock time patterns are parsed into time objects."""
    extractor = TimeAgentParameterExtractor(today=date(2026, 6, 29))

    parameters = extractor.extract("Imputa 2h hoy a las 9:00 para soporte")

    assert parameters.start_time == time(9, 0)


@pytest.mark.asyncio
async def test_should_mark_incomplete_parameters_when_start_time_missing() -> None:
    """Verify incomplete requests are flagged instead of guessing defaults."""
    agent = TimeAgent(
        memory_facade=FakeMemoryFacade(),
        clickup_time_tool=FakeClickUpTimeTool(),
        extractor=TimeAgentParameterExtractor(today=date(2026, 6, 29)),
    )

    result = await agent.process("Imputa 3h hoy al cliente Acme por revisión")

    assert result.success is False
    assert "hora de inicio" in result.answer


@pytest.mark.asyncio
async def test_should_generate_preview_for_complete_request(fixed_extractor: TimeAgentParameterExtractor) -> None:
    """Verify complete requests produce a safe preview and action payload."""
    agent = TimeAgent(
        memory_facade=FakeMemoryFacade(),
        clickup_time_tool=FakeClickUpTimeTool(),
        extractor=fixed_extractor,
    )

    result = await agent.process("Imputa 2h hoy a las 09:00 al cliente Acme por revisión del ticket 1001")

    assert result.success is True
    assert result.preview is not None
    assert result.preview["duration_minutes"] == 120
    assert result.preview["client_name"] == "Acme"
    assert result.action_payload["client_name"] == "Acme"
    assert result.action_payload["start_datetime"] == "2026-06-29T09:00:00"
    assert result.action_payload["end_datetime"] == "2026-06-29T11:00:00"


@pytest.mark.asyncio
async def test_should_build_short_task_name_from_description() -> None:
    """Verify task name is derived from the work description."""
    agent = TimeAgent(
        memory_facade=FakeMemoryFacade(),
        clickup_time_tool=FakeClickUpTimeTool(),
        extractor=TimeAgentParameterExtractor(today=date(2026, 6, 29)),
    )

    result = await agent.process("Imputa 1h hoy a las 10:00 por revisión del dashboard de métricas")

    assert result.success is True
    assert result.preview is not None
    assert "Revisión del dashboard" in result.preview["task_name"]


def test_should_approve_valid_save_time_entry_payload() -> None:
    """Verify safety policy accepts a well-formed save_time_entry action."""
    policy = AssistantSafetyPolicy()
    action = AssistantAction(
        id="action-1",
        action_type="save_time_entry",
        status="proposed",
        title="Imputar 60 min",
        description="Preview",
        payload={
            "task_name": "Soporte",
            "description": "Revisión",
            "start_datetime": "2026-06-29T09:00:00",
            "end_datetime": "2026-06-29T10:00:00",
            "client_name": "Acme",
        },
    )

    policy.ensure_can_execute(action)


def test_should_reject_save_time_entry_payload_missing_end_datetime() -> None:
    """Verify safety policy rejects incomplete save_time_entry payloads."""
    policy = AssistantSafetyPolicy()
    action = AssistantAction(
        id="action-1",
        action_type="save_time_entry",
        status="proposed",
        title="Imputar 60 min",
        description="Preview",
        payload={
            "task_name": "Soporte",
            "description": "Revisión",
            "start_datetime": "2026-06-29T09:00:00",
        },
    )

    with pytest.raises(ValueError, match="Invalid save_time_entry payload"):
        policy.ensure_can_execute(action)


@pytest.mark.asyncio
async def test_should_invoke_save_time_entry_tool_with_action_payload() -> None:
    """Verify executor passes the action payload to the ClickUp time tool."""
    action = AssistantAction(
        id="action-1",
        action_type="save_time_entry",
        status="proposed",
        title="Imputar 60 min",
        description="Preview",
        payload={
            "task_name": "Soporte",
            "description": "Revisión",
            "start_datetime": "2026-06-29T09:00:00",
            "end_datetime": "2026-06-29T10:00:00",
            "client_name": "Acme",
        },
    )

    async def get_action(action_id: str) -> AssistantAction:
        return action

    async def update_status(action_id: str, status: str, result: dict | None = None) -> AssistantAction:
        return AssistantAction(
            id=action_id,
            action_type="save_time_entry",
            status=status,
            title="Imputar 60 min",
            description="Preview",
            payload=action.payload,
            result=result,
            requires_approval=True,
        )

    class CapturingClickUpTimeTool(ClickUpTimeTool):
        """ClickUp time tool that records execution parameters."""

        def __init__(self) -> None:
            """Initialize with no state."""
            self.captured: dict = {}

        async def execute(self, **kwargs) -> ToolResult:
            """Record parameters and return a mock success result."""
            self.captured = kwargs
            return ToolResult.ok(data={"message": "MOCK: Time entry saved"})

    clickup_time_tool = CapturingClickUpTimeTool()
    repo = MagicMock()
    repo.get_action = get_action
    repo.update_status = update_status
    executor = AssistantActionExecutor(
        action_repository=repo,
        safety_policy=AssistantSafetyPolicy(),
        ticket_to_clickup_tool=MagicMock(),
        clickup_time_tool=clickup_time_tool,
        freshservice_adapter=MagicMock(),
    )

    await executor.approve("action-1")

    assert clickup_time_tool.captured["operation"] == "save"
    assert clickup_time_tool.captured["start_datetime"] == "2026-06-29T09:00:00"
    assert clickup_time_tool.captured["approved"] is True
