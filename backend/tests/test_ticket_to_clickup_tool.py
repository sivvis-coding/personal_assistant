"""Tests for TicketToClickUpTool."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.ai import UserStory
from app.schemas.clickup import ClickUpTaskResult
from app.tools.base import ToolResult
from app.tools.ticket_to_clickup.tool import TicketToClickUpTool


def _build_tool(
    *,
    ticket_service: MagicMock | None = None,
    ai_service: MagicMock | None = None,
    ai_draft_repository: MagicMock | None = None,
    integration_link_repository: MagicMock | None = None,
    workflow_run_repository: MagicMock | None = None,
    clickup_client: MagicMock | None = None,
) -> TicketToClickUpTool:
    """Build a tool with deterministic mock dependencies."""
    return TicketToClickUpTool(
        ticket_service=ticket_service or MagicMock(),
        ai_service=ai_service or MagicMock(),
        ai_draft_repository=ai_draft_repository or MagicMock(),
        integration_link_repository=integration_link_repository or MagicMock(),
        workflow_run_repository=workflow_run_repository or MagicMock(),
        clickup_client=clickup_client,
    )


@pytest.mark.asyncio
async def test_should_return_error_for_unknown_operation() -> None:
    """Unknown operations return a failed ToolResult."""
    tool = _build_tool()

    result = await tool.execute(operation="invalid", ticket_id="123")

    assert result.success is False
    assert "Unknown operation" in result.message


@pytest.mark.asyncio
async def test_should_return_error_when_ticket_id_missing_for_prepare() -> None:
    """Prepare without ticket_id returns a failed ToolResult."""
    tool = _build_tool()

    result = await tool.execute(operation="prepare")

    assert result.success is False
    assert "Missing required parameter 'ticket_id'" in result.message


@pytest.mark.asyncio
async def test_should_prepare_task_without_clickup_client() -> None:
    """Prepare generates a user story and draft without ClickUp client."""
    user_story = UserStory(
        title="Test story",
        description="Description",
        acceptance_criteria_in_gerkin="Given...",
        constraints="None",
        user_story_statement="As a user...",
        out_of_scope="None",
        requested_by="User",
        functional_description="Does something",
    )
    ticket_service = MagicMock()
    ticket_service.get_ticket = AsyncMock(return_value=MagicMock(ticket=MagicMock()))
    ai_service = MagicMock()
    ai_service.ticket_to_user_story = AsyncMock(return_value=user_story)
    ai_service.model_name = "gpt-test"
    ai_draft_repository = MagicMock()
    ai_draft_repository.save_draft = AsyncMock(return_value="draft-1")
    workflow_run_repository = MagicMock()
    workflow_run_repository.start = AsyncMock(return_value="run-1")
    workflow_run_repository.finish_success = AsyncMock()

    tool = _build_tool(
        ticket_service=ticket_service,
        ai_service=ai_service,
        ai_draft_repository=ai_draft_repository,
        workflow_run_repository=workflow_run_repository,
    )

    result = await tool.execute(operation="prepare", ticket_id="TICKET-42")

    assert result.success is True
    assert result.data["ticket_id"] == "TICKET-42"
    assert result.data["requires_approval"] is True
    ticket_service.get_ticket.assert_awaited_once_with("TICKET-42")
    ai_service.ticket_to_user_story.assert_awaited_once()
    ai_draft_repository.save_draft.assert_awaited_once()


@pytest.mark.asyncio
async def test_should_create_clickup_task_on_approve() -> None:
    """Approve creates a ClickUp task and stores the integration link."""
    user_story = UserStory(
        title="Test story",
        description="Description",
        acceptance_criteria_in_gerkin="Given...",
        constraints="None",
        user_story_statement="As a user...",
        out_of_scope="None",
        requested_by="User",
        functional_description="Does something",
    )
    ticket_service = MagicMock()
    ticket_service.get_ticket = AsyncMock(return_value=MagicMock(ticket=MagicMock()))
    integration_link_repository = MagicMock()
    integration_link_repository.find_link = AsyncMock(return_value=None)
    integration_link_repository.save_link = AsyncMock(return_value="link-1")
    workflow_run_repository = MagicMock()
    workflow_run_repository.start = AsyncMock(return_value="run-1")
    workflow_run_repository.finish_success = AsyncMock()
    clickup_client = MagicMock()
    clickup_client.create_task_from_ticket = AsyncMock(
        return_value=ClickUpTaskResult(id="task-1", url="http://clickup/task-1", source="clickup")
    )

    tool = _build_tool(
        ticket_service=ticket_service,
        integration_link_repository=integration_link_repository,
        workflow_run_repository=workflow_run_repository,
        clickup_client=clickup_client,
    )

    result = await tool.execute(operation="approve", ticket_id="TICKET-42", user_story=user_story.model_dump())

    assert result.success is True
    assert result.data["clickup_task"]["id"] == "task-1"
    clickup_client.create_task_from_ticket.assert_awaited_once()
    integration_link_repository.save_link.assert_awaited_once()


@pytest.mark.asyncio
async def test_should_reuse_existing_link_on_approve() -> None:
    """Approve returns cached task when an integration link already exists."""
    user_story = UserStory(
        title="Test story",
        description="Description",
        acceptance_criteria_in_gerkin="Given...",
        constraints="None",
        user_story_statement="As a user...",
        out_of_scope="None",
        requested_by="User",
        functional_description="Does something",
    )
    ticket_service = MagicMock()
    ticket_service.get_ticket = AsyncMock(return_value=MagicMock(ticket=MagicMock()))
    integration_link_repository = MagicMock()
    integration_link_repository.find_link = AsyncMock(
        return_value={
            "id": "link-1",
            "target_id": "task-1",
            "target_url": "http://clickup/task-1",
        }
    )
    workflow_run_repository = MagicMock()
    workflow_run_repository.start = AsyncMock(return_value="run-1")
    workflow_run_repository.finish_success = AsyncMock()
    clickup_client = MagicMock()

    tool = _build_tool(
        ticket_service=ticket_service,
        integration_link_repository=integration_link_repository,
        workflow_run_repository=workflow_run_repository,
        clickup_client=clickup_client,
    )

    result = await tool.execute(operation="approve", ticket_id="TICKET-42", user_story=user_story.model_dump())

    assert result.success is True
    assert result.data["clickup_task"]["source"] == "cache"
    clickup_client.create_task_from_ticket.assert_not_called()
    integration_link_repository.save_link.assert_not_called()


@pytest.mark.asyncio
async def test_should_fail_approve_without_clickup_client() -> None:
    """Approve fails when the tool was created without a ClickUp client."""
    user_story = UserStory(
        title="Test story",
        description="Description",
        acceptance_criteria_in_gerkin="Given...",
        constraints="None",
        user_story_statement="As a user...",
        out_of_scope="None",
        requested_by="User",
        functional_description="Does something",
    )
    tool = _build_tool()

    result = await tool.execute(operation="approve", ticket_id="TICKET-42", user_story=user_story.model_dump())

    assert result.success is False
    assert "ClickUp client is required" in result.message
