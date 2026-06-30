"""Tests for ClickUpStatusSyncService.

Covers the three core behavioural contracts:
  1. When a ClickUp task status differs from the stored status, a private
     Freshservice note is posted and the link's stored status is updated.
  2. When the status is unchanged, no note is posted and the stored status
     is not updated.
  3. When one link fails (e.g. adapter raises), processing continues for the
     remaining links and the failed link is recorded with action "error".
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.clickup import ClickUpTask
from app.services.clickup_status_sync_service import ClickUpStatusSyncService
from app.tools.freshservice.schemas import UpdateTicketInput


def _build_service(
    *,
    links: list[dict] | None = None,
    tasks: list[ClickUpTask] | None = None,
    note_side_effect=None,
    update_link_side_effect=None,
) -> tuple[ClickUpStatusSyncService, MagicMock, MagicMock, MagicMock]:
    """Build a ClickUpStatusSyncService with controlled mock dependencies.

    Parameters:
        links: Integration link documents returned by the repository.
        tasks: ClickUp tasks returned by the client.
        note_side_effect: Optional side_effect for adapter.update_ticket.
        update_link_side_effect: Optional side_effect for repository.update_link_status.

    Returns:
        Tuple of (service, link_repository_mock, clickup_client_mock, freshservice_adapter_mock).
    """
    link_repo = MagicMock()
    link_repo.find_all_by_relation_type = AsyncMock(return_value=links or [])
    link_repo.update_link_status = AsyncMock(side_effect=update_link_side_effect)

    clickup_client = MagicMock()
    clickup_client.list_tasks = AsyncMock(return_value=tasks or [])

    adapter = MagicMock()
    adapter.update_ticket = AsyncMock(
        side_effect=note_side_effect,
        return_value={"id": "note-1", "private": True},
    )

    service = ClickUpStatusSyncService(link_repo, clickup_client, adapter)
    return service, link_repo, clickup_client, adapter


# ---------------------------------------------------------------------------
# test_sync_posts_note_when_status_changed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_posts_note_when_status_changed() -> None:
    """When ClickUp returns a different status than stored, a private note is posted.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        The stored status is updated after the note is posted so the same
        change is never reported twice.
    """
    links = [
        {
            "id": "link-1",
            "source_id": "ticket-42",
            "target_id": "task-99",
            "last_known_clickup_status": "open",
        }
    ]
    tasks = [ClickUpTask(id="task-99", name="Support request", status="in progress")]

    service, link_repo, _, adapter = _build_service(links=links, tasks=tasks)

    results = await service.sync_all()

    assert len(results) == 1
    result = results[0]
    assert result["ticket_id"] == "ticket-42"
    assert result["task_id"] == "task-99"
    assert result["old_status"] == "open"
    assert result["new_status"] == "in progress"
    assert result["action"] == "noted"

    # Verify the private note was posted with the correct text.
    adapter.update_ticket.assert_awaited_once()
    call_args = adapter.update_ticket.call_args[0][0]
    assert isinstance(call_args, UpdateTicketInput)
    assert call_args.ticket_id == "ticket-42"
    assert "Support request" in call_args.changes["note"]
    assert "in progress" in call_args.changes["note"]

    # Verify the stored status was updated.
    link_repo.update_link_status.assert_awaited_once_with("link-1", "in progress")


# ---------------------------------------------------------------------------
# test_sync_skips_when_status_unchanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_skips_when_status_unchanged() -> None:
    """When the ClickUp status matches the stored status, no note is posted.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Neither update_ticket nor update_link_status must be called when
        nothing changed.
    """
    links = [
        {
            "id": "link-1",
            "source_id": "ticket-42",
            "target_id": "task-99",
            "last_known_clickup_status": "in progress",
        }
    ]
    tasks = [ClickUpTask(id="task-99", name="Support request", status="in progress")]

    service, link_repo, _, adapter = _build_service(links=links, tasks=tasks)

    results = await service.sync_all()

    assert len(results) == 1
    result = results[0]
    assert result["action"] == "unchanged"
    assert result["new_status"] == "in progress"

    adapter.update_ticket.assert_not_awaited()
    link_repo.update_link_status.assert_not_awaited()


# ---------------------------------------------------------------------------
# test_sync_continues_after_per_link_error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_continues_after_per_link_error() -> None:
    """When one link's note posting fails, remaining links still process.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        The failing link is recorded with action "error"; the second link
        must be processed normally and its note must be posted.
    """
    links = [
        {
            "id": "link-1",
            "source_id": "ticket-10",
            "target_id": "task-10",
            "last_known_clickup_status": "open",
        },
        {
            "id": "link-2",
            "source_id": "ticket-20",
            "target_id": "task-20",
            "last_known_clickup_status": "open",
        },
    ]
    tasks = [
        ClickUpTask(id="task-10", name="First task", status="in progress"),
        ClickUpTask(id="task-20", name="Second task", status="done"),
    ]

    call_count = 0

    async def failing_first_call(input_data):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Fresh API unavailable")
        return {"id": "note-2", "private": True}

    service, link_repo, _, adapter = _build_service(
        links=links,
        tasks=tasks,
        note_side_effect=failing_first_call,
    )

    results = await service.sync_all()

    assert len(results) == 2

    first = results[0]
    assert first["ticket_id"] == "ticket-10"
    assert first["action"] == "error"
    assert "Fresh API unavailable" in str(first.get("error", ""))

    second = results[1]
    assert second["ticket_id"] == "ticket-20"
    assert second["action"] == "noted"
    assert second["new_status"] == "done"

    # The second link's stored status must still be updated.
    link_repo.update_link_status.assert_awaited_once_with("link-2", "done")


# ---------------------------------------------------------------------------
# test_sync_handles_first_run_with_no_stored_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_handles_first_run_with_no_stored_status() -> None:
    """On first run, last_known_clickup_status is None — any status triggers a note.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        None != "open" so the first sync after link creation always posts a
        note, making the initial status visible in Freshservice.
    """
    links = [
        {
            "id": "link-1",
            "source_id": "ticket-42",
            "target_id": "task-99",
            "last_known_clickup_status": None,
        }
    ]
    tasks = [ClickUpTask(id="task-99", name="New task", status="open")]

    service, link_repo, _, adapter = _build_service(links=links, tasks=tasks)

    results = await service.sync_all()

    assert len(results) == 1
    assert results[0]["action"] == "noted"
    assert results[0]["old_status"] is None
    assert results[0]["new_status"] == "open"
    adapter.update_ticket.assert_awaited_once()
    link_repo.update_link_status.assert_awaited_once_with("link-1", "open")


# ---------------------------------------------------------------------------
# test_sync_records_task_not_found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_records_task_not_found() -> None:
    """When a linked task no longer exists in ClickUp, action is "task_not_found".

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        No note is posted and the stored status is not updated.
    """
    links = [
        {
            "id": "link-1",
            "source_id": "ticket-42",
            "target_id": "task-deleted",
            "last_known_clickup_status": "open",
        }
    ]
    # ClickUp returns tasks but the linked task ID is absent.
    tasks = [ClickUpTask(id="task-other", name="Unrelated task", status="open")]

    service, link_repo, _, adapter = _build_service(links=links, tasks=tasks)

    results = await service.sync_all()

    assert len(results) == 1
    assert results[0]["action"] == "task_not_found"
    adapter.update_ticket.assert_not_awaited()
    link_repo.update_link_status.assert_not_awaited()


# ---------------------------------------------------------------------------
# test_sync_returns_empty_when_no_links
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_returns_empty_when_no_links() -> None:
    """When there are no ticket_to_task links, sync_all returns an empty list.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        ClickUp should not be called when there are no links to process.
    """
    service, _, clickup_client, adapter = _build_service(links=[])

    results = await service.sync_all()

    assert results == []
    clickup_client.list_tasks.assert_not_awaited()
    adapter.update_ticket.assert_not_awaited()


# ---------------------------------------------------------------------------
# test_sync_records_error_when_clickup_list_tasks_fails
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_records_error_when_clickup_list_tasks_fails() -> None:
    """When ClickUp.list_tasks() raises, all links are recorded with action "error".

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        The error must not propagate; the caller receives a structured error
        list instead.
    """
    links = [
        {
            "id": "link-1",
            "source_id": "ticket-42",
            "target_id": "task-99",
            "last_known_clickup_status": "open",
        }
    ]

    link_repo = MagicMock()
    link_repo.find_all_by_relation_type = AsyncMock(return_value=links)
    link_repo.update_link_status = AsyncMock()

    clickup_client = MagicMock()
    clickup_client.list_tasks = AsyncMock(side_effect=RuntimeError("ClickUp down"))

    adapter = MagicMock()
    adapter.update_ticket = AsyncMock()

    service = ClickUpStatusSyncService(link_repo, clickup_client, adapter)

    results = await service.sync_all()

    assert len(results) == 1
    assert results[0]["action"] == "error"
    assert "ClickUp down" in str(results[0].get("error", ""))
    adapter.update_ticket.assert_not_awaited()
    link_repo.update_link_status.assert_not_awaited()
