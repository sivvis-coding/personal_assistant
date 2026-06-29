import pytest

from app.tools.clickup_time_tracking import build_time_entry_preview, calculate_duration_minutes, parse_datetime_to_utc_ms, save_time_entry


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
    result = save_time_entry.invoke({"time_entry": time_entry})

    # Assert
    assert "Explicit approval is required" in result
