"""Tests for the migrated time agent and related safety/execution flows.

These tests used to import the legacy app.assistant.agents.time_agent module.
They now exercise the migrated app.agents.time.agent implementation, which
extracts activities via an injected narrative extractor (faked here) instead
of the retired regex-based extractor.
"""

from datetime import date, time
from unittest.mock import MagicMock

import pytest

from app.agents.time.agent import TimeAgent
from app.agents.time.schemas import TimeEntryParameters
from app.assistant.action_executor import AssistantActionExecutor
from app.assistant.safety_policy import AssistantSafetyPolicy
from app.assistant.schemas.actions import AssistantAction
from app.core.memory.interface import AgentMemory, MemoryConfig
from app.schemas.settings import AppSettings
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
    """Fake ClickUp time tool returning deterministic previews and clients."""

    name = "clickup_time"
    description = "Fake ClickUp time tool"
    parameters = []

    def __init__(self, clients: list[str] | None = None) -> None:
        self._clients = clients or []

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
        return ToolResult.ok(data={"clients": self._clients})


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


def _agent(activities: list[TimeEntryParameters], clients: list[str] | None = None) -> TimeAgent:
    return TimeAgent(
        memory_facade=FakeMemoryFacade(),
        narrative_extractor=FakeNarrativeExtractor(activities),
        settings_service=FakeSettingsService(),
        clickup_time_tool=FakeClickUpTimeTool(clients=clients),
    )


@pytest.mark.asyncio
async def test_should_mark_incomplete_parameters_when_start_time_missing() -> None:
    """Verify incomplete requests are flagged instead of guessing defaults."""
    activity = TimeEntryParameters(
        task_name="Revisión",
        client_name="Acme",
        description="Revisión de ticket",
        duration_minutes=180,
        start_date=date(2026, 6, 29),
        start_time=None,
    )
    agent = _agent([activity])

    result = await agent.process("Imputa 3h hoy al cliente Acme por revisión")

    assert result.success is False
    assert len(result.activities) == 1
    assert "hora de inicio" in result.activities[0].answer


@pytest.mark.asyncio
async def test_should_generate_preview_for_complete_request() -> None:
    """Verify complete requests produce a safe preview and action payload."""
    activity = TimeEntryParameters(
        task_name="Revisión del ticket 1001",
        client_name="Acme",
        description="Revisión del ticket 1001",
        duration_minutes=120,
        start_date=date(2026, 6, 29),
        start_time=time(9, 0),
    )
    agent = _agent([activity], clients=["Acme"])

    result = await agent.process("Imputa 2h hoy a las 09:00 al cliente Acme por revisión del ticket 1001")

    assert result.success is True
    resolved = result.activities[0]
    assert resolved.preview is not None
    assert resolved.preview["duration_minutes"] == 120
    assert resolved.preview["client_name"] == "Acme"
    assert resolved.action_payload["client_name"] == "Acme"
    assert resolved.action_payload["start_datetime"] == "2026-06-29T09:00:00"
    assert resolved.action_payload["end_datetime"] == "2026-06-29T11:00:00"


@pytest.mark.asyncio
async def test_should_resolve_multiple_activities_independently() -> None:
    """Verify a narrative with several activities produces independent resolutions."""
    activities = [
        TimeEntryParameters(
            task_name="Revisión tickets",
            client_name="Acme",
            description="Revisión de tickets",
            duration_minutes=120,
            start_date=date(2026, 6, 29),
            start_time=time(9, 0),
        ),
        TimeEntryParameters(
            task_name="Propuesta",
            client_name="Beta",
            description="Preparación de propuesta",
            duration_minutes=60,
            start_date=date(2026, 6, 29),
            start_time=time(11, 0),
        ),
    ]
    agent = _agent(activities, clients=["Acme", "Beta"])

    result = await agent.process("Hoy 2h con Acme revisando tickets y 1h con Beta en una propuesta")

    assert result.success is True
    assert len(result.activities) == 2
    assert all(activity.success for activity in result.activities)
    assert result.activities[0].action_payload["client_name"] == "Acme"
    assert result.activities[1].action_payload["client_name"] == "Beta"


@pytest.mark.asyncio
async def test_should_ask_for_client_clarification_without_blocking_other_activities() -> None:
    """Verify an ambiguous client only pends its own activity, not the whole batch."""
    activities = [
        TimeEntryParameters(
            task_name="Revisión tickets",
            client_name="Acem",  # typo, ambiguous against "Acme"
            description="Revisión de tickets",
            duration_minutes=120,
            start_date=date(2026, 6, 29),
            start_time=time(9, 0),
        ),
        TimeEntryParameters(
            task_name="Propuesta",
            client_name="Beta",
            description="Preparación de propuesta",
            duration_minutes=60,
            start_date=date(2026, 6, 29),
            start_time=time(11, 0),
        ),
    ]
    agent = _agent(activities, clients=["Acme", "Beta"])

    result = await agent.process("Hoy 2h con Acem revisando tickets y 1h con Beta en una propuesta")

    assert result.success is True  # Beta activity still resolved
    ambiguous, resolved = result.activities
    assert ambiguous.needs_clarification is True
    assert "Acme" in ambiguous.candidate_clients
    assert resolved.success is True
    assert resolved.action_payload["client_name"] == "Beta"


@pytest.mark.asyncio
async def test_should_resolve_pending_activity_with_confirmed_client() -> None:
    """Verify resolve_pending_activity resolves a queued activity without re-extracting."""
    agent = _agent([], clients=["Acme"])
    parameters = TimeEntryParameters(
        task_name="Revisión tickets",
        client_name="",
        description="Revisión de tickets",
        duration_minutes=120,
        start_date=date(2026, 6, 29),
        start_time=time(9, 0),
    )

    resolution = await agent.resolve_pending_activity(parameters, "Acme", list_id="list-1")

    assert resolution.success is True
    assert resolution.action_payload["client_name"] == "Acme"


@pytest.mark.asyncio
async def test_should_report_when_no_personal_list_is_configured() -> None:
    """Verify the agent asks the user to configure a personal list before extracting."""
    agent = TimeAgent(
        memory_facade=FakeMemoryFacade(),
        narrative_extractor=FakeNarrativeExtractor([]),
        settings_service=FakeSettingsService(list_id=""),
        clickup_time_tool=FakeClickUpTimeTool(),
    )

    result = await agent.process("Imputa 1h hoy por soporte")

    assert result.success is False
    assert "lista personal" in result.answer


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
    """Verify executor resolves the personal list and passes the payload to the ClickUp time tool."""
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
        settings_service=FakeSettingsService(list_id="list-1"),
    )

    await executor.approve("action-1")

    assert clickup_time_tool.captured["operation"] == "save"
    assert clickup_time_tool.captured["list_id"] == "list-1"
    assert clickup_time_tool.captured["start_datetime"] == "2026-06-29T09:00:00"
    assert clickup_time_tool.captured["approved"] is True


@pytest.mark.asyncio
async def test_should_fail_save_time_entry_when_no_personal_list_configured() -> None:
    """Verify the executor fails clearly instead of saving to an unknown list."""
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

    repo = MagicMock()
    repo.get_action = get_action
    repo.update_status = update_status
    executor = AssistantActionExecutor(
        action_repository=repo,
        safety_policy=AssistantSafetyPolicy(),
        ticket_to_clickup_tool=MagicMock(),
        clickup_time_tool=MagicMock(),
        freshservice_adapter=MagicMock(),
        settings_service=FakeSettingsService(list_id=""),
    )

    result = await executor.approve("action-1")

    assert result.status == "failed"
