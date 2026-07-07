"""Tests for the single-approval (single-phase) ClickUp task creation flow."""

import pytest

from app.assistant.action_executor import AssistantActionExecutor
from app.assistant.safety_policy import AssistantSafetyPolicy
from app.assistant.schemas.actions import AssistantAction
from app.tools.base import ToolResult

_USER_STORY = {"title": "Hacer X", "description": "algo"}


class FakeActionRepo:
    """In-memory action repository recording follow-up creations."""

    def __init__(self, action: AssistantAction) -> None:
        self._actions = {action.id: action}
        self.created: list = []

    async def get_action(self, action_id: str) -> AssistantAction | None:
        return self._actions.get(action_id)

    async def update_status(self, action_id: str, status: str, result: dict | None = None) -> AssistantAction:
        current = self._actions[action_id]
        updated = current.model_copy(update={"status": status, "result": result})
        self._actions[action_id] = updated
        return updated

    async def create_action(self, action_create) -> AssistantAction:  # noqa: ANN001
        # A second (follow-up) action would mean the two-phase flow is back.
        self.created.append(action_create)
        raise AssertionError("Single-phase flow must not create a follow-up action.")


class FakeTicketToClickUp:
    """Records tool operations; approve ops return a created task URL."""

    def __init__(self) -> None:
        self.operations: list[str] = []

    async def execute(self, **kwargs) -> ToolResult:  # noqa: ANN003
        operation = kwargs.get("operation")
        self.operations.append(operation)
        if operation in ("prepare", "prepare_standalone"):
            return ToolResult.ok(data={"user_story": _USER_STORY})
        if operation == "approve":
            return ToolResult.ok(data={"clickup_task": {"url": "https://app.clickup.com/t/abc"}})
        if operation == "approve_standalone":
            return ToolResult.ok(data={"clickup_task": {"url": "https://app.clickup.com/t/def"}})
        return ToolResult.error(message=f"unexpected op {operation}")


class FakeFreshAdapter:
    def __init__(self) -> None:
        self.replies: list[str] = []
        self.clickup_urls: list[str] = []

    async def reply_ticket(self, payload) -> dict:  # noqa: ANN001
        self.replies.append(payload.body)
        return {"ok": True}

    async def set_clickup_url(self, ticket_id: str, url: str) -> None:
        self.clickup_urls.append(url)


def _make_executor(action: AssistantAction) -> tuple[AssistantActionExecutor, FakeActionRepo, FakeTicketToClickUp, FakeFreshAdapter]:
    repo = FakeActionRepo(action)
    tool = FakeTicketToClickUp()
    fresh = FakeFreshAdapter()
    executor = AssistantActionExecutor(
        action_repository=repo,
        safety_policy=AssistantSafetyPolicy(),
        ticket_to_clickup_tool=tool,
        clickup_time_tool=None,
        freshservice_adapter=fresh,
    )
    return executor, repo, tool, fresh


def _action(action_type: str, payload: dict, ticket_id: str | None = None) -> AssistantAction:
    return AssistantAction(
        id="a1",
        action_type=action_type,
        status="proposed",
        title="t",
        description="d",
        ticket_id=ticket_id,
        payload=payload,
    )


@pytest.mark.asyncio
async def test_send_ticket_to_backlog_single_approval_creates_and_replies() -> None:
    """With a user story in payload, one approval creates the task and replies — no follow-up."""
    action = _action("send_ticket_to_backlog", {"user_story": _USER_STORY, "body": "Hola"}, ticket_id="1001")
    executor, repo, tool, fresh = _make_executor(action)

    result = await executor.approve("a1")

    assert result.status == "completed"
    assert "approve" in tool.operations
    assert "prepare" not in tool.operations  # user story already present
    assert repo.created == []  # no second approval action
    assert fresh.clickup_urls == ["https://app.clickup.com/t/abc"]
    assert "Tarea en ClickUp: https://app.clickup.com/t/abc" in fresh.replies[0]


@pytest.mark.asyncio
async def test_prepare_clickup_us_single_approval_creates_standalone() -> None:
    """A standalone US action creates the task on one approval — no follow-up."""
    action = _action("prepare_clickup_us", {"user_story": _USER_STORY, "description": "algo"})
    executor, repo, tool, _ = _make_executor(action)

    result = await executor.approve("a1")

    assert result.status == "completed"
    assert "approve_standalone" in tool.operations
    assert repo.created == []


@pytest.mark.asyncio
async def test_backlog_without_user_story_regenerates_as_fallback() -> None:
    """When the payload has no user story, the executor generates one before creating."""
    action = _action("send_ticket_to_backlog", {"body": "Hola"}, ticket_id="1001")
    executor, _, tool, _ = _make_executor(action)

    result = await executor.approve("a1")

    assert result.status == "completed"
    assert tool.operations == ["prepare", "approve"]  # generated, then created
