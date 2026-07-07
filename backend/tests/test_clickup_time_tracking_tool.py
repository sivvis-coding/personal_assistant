from unittest.mock import MagicMock, patch

import pytest

from app.tools.clickup_time.tool import ClickUpTimeTool
from app.tools.clickup_time_tracking import (
    _authenticated_user_cache,
    _client_field_cache,
    _create_clickup_task,
    _find_client_field,
    _get_authenticated_user_id,
    build_time_entry_preview,
    calculate_duration_minutes,
    parse_datetime_to_utc_ms,
    save_time_entry,
)


def test_should_parse_madrid_local_datetime_to_unix_milliseconds() -> None:
    """Verify local Madrid datetime parsing returns Unix milliseconds.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Europe/Madrid winter offset is UTC+1 for this date.
    """
    # Arrange
    datetime_text = "2025-01-15T09:00:00"

    # Act
    timestamp_ms = parse_datetime_to_utc_ms(datetime_text)

    # Assert
    assert timestamp_ms == 1_736_928_000_000


def test_should_calculate_duration_minutes_when_end_is_after_start() -> None:
    """Verify duration calculation for a valid time range.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Duration uses whole minutes from Unix millisecond values.
    """
    # Arrange
    start_ms = 1_000_000
    end_ms = start_ms + 90 * 60_000

    # Act
    duration_minutes = calculate_duration_minutes(start_ms, end_ms)

    # Assert
    assert duration_minutes == 90


def test_should_return_error_when_end_is_not_after_start() -> None:
    """Verify invalid time ranges are rejected.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Equal start and end would create a zero-duration ClickUp entry.
    """
    # Arrange
    start_ms = 1_000_000
    end_ms = 1_000_000

    # Act / Assert
    with pytest.raises(ValueError, match="end_datetime must be after start_datetime"):
        calculate_duration_minutes(start_ms, end_ms)


def test_should_build_preview_without_external_side_effects() -> None:
    """Verify preview calculates duration without requiring ClickUp credentials.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Preview intentionally does not validate client existence in ClickUp.
    """
    # Arrange
    time_entry = {
        "task_name": "Support work",
        "description": "Investigate ticket",
        "start_datetime": "2025-01-15T09:00:00",
        "end_datetime": "2025-01-15T10:30:00",
        "client_name": "Client A",
    }

    # Act
    preview = build_time_entry_preview(time_entry)

    # Assert
    assert preview["duration_minutes"] == 90
    assert preview["task_name"] == "Support work"


def test_should_return_error_when_saving_time_entry_without_approval() -> None:
    """Verify save_time_entry requires explicit approval.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Approval is checked before credentials or network calls.
    """
    # Arrange
    time_entry = {
        "task_name": "Support work",
        "description": "Investigate ticket",
        "start_datetime": "2025-01-15T09:00:00",
        "end_datetime": "2025-01-15T10:30:00",
        "client_name": "Client A",
    }

    # Act
    result = save_time_entry(time_entry, "list-1")

    # Assert
    assert "Explicit approval is required" in result


def test_should_cache_client_field_lookup_per_list() -> None:
    """Verify the client custom field is fetched from ClickUp once per list and
    reused on subsequent calls, so a chat session does not hit the ClickUp API
    on every message just to know the client field's dropdown options.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        The cache is keyed by list_id, isolated per test via an explicit clear.
    """
    # Arrange
    _client_field_cache.clear()
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "fields": [{"id": "field-1", "name": "Cliente", "type": "drop_down", "type_config": {"options": []}}]
    }

    with patch("app.tools.clickup_time_tracking.httpx.get", return_value=fake_response) as mock_get:
        first = _find_client_field("list-cache-test")
        second = _find_client_field("list-cache-test")

    # Assert
    assert first == second == {"id": "field-1", "name": "Cliente", "type": "drop_down", "type_config": {"options": []}}
    assert mock_get.call_count == 1


@pytest.mark.asyncio
async def test_should_surface_save_time_entry_errors_as_a_failed_tool_result() -> None:
    """Verify ClickUpTimeTool reports failures instead of silently succeeding.

    Regression test: save_time_entry() returns "ERROR: ..." strings rather than
    raising, so the tool must detect that prefix and return ToolResult.error —
    otherwise a failed ClickUp write (missing approval, unresolved client, etc.)
    would be reported to the caller as a success.

    Parameters:
        None.

    Returns:
        None.
    """
    # Arrange
    tool = ClickUpTimeTool()

    # Act: omit approved=True so save_time_entry() returns an ERROR string
    result = await tool.execute(
        operation="save",
        list_id="list-1",
        task_name="Support work",
        description="Investigate ticket",
        start_datetime="2025-01-15T09:00:00",
        end_datetime="2025-01-15T10:30:00",
        client_name="Client A",
    )

    # Assert
    assert result.success is False
    assert "Explicit approval is required" in result.message


def test_should_resolve_and_cache_authenticated_user_id() -> None:
    """Verify the authenticated ClickUp user id is fetched once and cached.

    Used to self-assign created tasks to the token's owner.

    Parameters:
        None.

    Returns:
        None.
    """
    # Arrange
    _authenticated_user_cache.clear()
    fake_settings = MagicMock(clickup_api_key="fake-key")
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"user": {"id": 4242, "username": "ivan"}}

    with patch("app.tools.clickup_time_tracking.get_settings", return_value=fake_settings), \
         patch("app.tools.clickup_time_tracking.httpx.get", return_value=fake_response) as mock_get:
        first = _get_authenticated_user_id()
        second = _get_authenticated_user_id()

    # Assert
    assert first == second == 4242
    assert mock_get.call_count == 1


def test_should_include_assignee_in_create_task_payload() -> None:
    """Verify _create_clickup_task sends the assignee when one is resolved.

    Parameters:
        None.

    Returns:
        None.
    """
    # Arrange
    fake_settings = MagicMock(clickup_api_key="fake-key")
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"id": "task-1", "url": "https://app.clickup.com/t/task-1"}

    with patch("app.tools.clickup_time_tracking.get_settings", return_value=fake_settings), \
         patch("app.tools.clickup_time_tracking.httpx.post", return_value=fake_response) as mock_post:
        _create_clickup_task(
            list_id="list-1",
            name="Support work",
            description="Investigate ticket",
            custom_fields=None,
            status=None,
            start_date_ms=1_000_000,
            due_date_ms=2_000_000,
            assignee_id=4242,
        )

    # Assert
    sent_payload = mock_post.call_args.kwargs["json"]
    assert sent_payload["assignees"] == [4242]


def test_should_omit_assignee_when_not_resolved() -> None:
    """Verify _create_clickup_task omits assignees when no user id was resolved."""
    # Arrange
    fake_settings = MagicMock(clickup_api_key="fake-key")
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"id": "task-1", "url": "https://app.clickup.com/t/task-1"}

    with patch("app.tools.clickup_time_tracking.get_settings", return_value=fake_settings), \
         patch("app.tools.clickup_time_tracking.httpx.post", return_value=fake_response) as mock_post:
        _create_clickup_task(
            list_id="list-1",
            name="Support work",
            description="Investigate ticket",
            custom_fields=None,
            status=None,
            start_date_ms=1_000_000,
            due_date_ms=2_000_000,
        )

    # Assert
    sent_payload = mock_post.call_args.kwargs["json"]
    assert "assignees" not in sent_payload
