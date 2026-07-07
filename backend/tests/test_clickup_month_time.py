"""Tests for the monthly ClickUp time calendar."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.integrations.clickup import ClickUpClient


@pytest.mark.asyncio
async def test_should_return_mock_month_time_entries_without_credentials() -> None:
    """Verify missing credentials produce a full month of mock day summaries.

    Parameters:
        None.

    Returns:
        None.
    """
    client = ClickUpClient(Settings())

    result = await client.get_month_time_entries(2026, 6)

    assert result.source == "mock"
    assert result.year == 2026
    assert result.month == 6
    assert len(result.days) == 30  # June has 30 days
    assert result.days[0].date == date(2026, 6, 1)
    assert result.days[0].total_hours == 2.5
    assert all(day.total_hours == 0 for day in result.days[1:])


@pytest.mark.asyncio
async def test_should_group_real_time_entries_by_day() -> None:
    """Verify time entries are grouped into their calendar day, days without entries get zero.

    Parameters:
        None.

    Returns:
        None.
    """
    settings = Settings(clickup_api_key="key", clickup_team_id="team", clickup_list_id="list")
    client = ClickUpClient(settings)

    day1_start_ms = int(datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc).timestamp() * 1000)
    day3_start_ms = int(datetime(2026, 6, 3, 9, 0, tzinfo=timezone.utc).timestamp() * 1000)

    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "data": [
            {"task": {"id": "t1", "name": "Task 1"}, "start": day1_start_ms, "duration": 2 * 3_600_000},
            {"task": {"id": "t2", "name": "Task 2"}, "start": day3_start_ms, "duration": 1 * 3_600_000},
        ]
    }

    fake_client = AsyncMock()
    fake_client.get.return_value = fake_response
    fake_client.__aenter__.return_value = fake_client
    fake_client.__aexit__.return_value = False

    with patch("app.integrations.clickup.httpx.AsyncClient", return_value=fake_client):
        result = await client.get_month_time_entries(2026, 6)

    assert result.source == "clickup"
    assert len(result.days) == 30

    by_date = {day.date: day for day in result.days}
    assert by_date[date(2026, 6, 1)].total_hours == 2.0
    assert by_date[date(2026, 6, 2)].total_hours == 0
    assert by_date[date(2026, 6, 3)].total_hours == 1.0
    assert result.total_hours == 3.0
