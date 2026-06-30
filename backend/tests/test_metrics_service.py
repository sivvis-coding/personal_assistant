from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.ai import UserStory
from app.schemas.clickup import ClickUpTask, TimeEntry, WeekTimeResponse
from app.schemas.ticket import Ticket, TicketListResponse, TicketRequester
from app.services.metrics_service import MetricsService


def _build_ticket(status: str, due_by: str | None = None, tags: list[str] | None = None) -> Ticket:
    """Build a ticket with given status and raw metadata."""
    raw: dict = {}
    if due_by:
        raw["due_by"] = due_by
    if tags:
        raw["tags"] = tags
    return Ticket(
        id="123",
        subject="Test",
        status=status,
        priority="medium",
        requester=TicketRequester(name="User"),
        raw=raw,
    )


@pytest.mark.asyncio
async def test_should_count_open_and_overdue_tickets() -> None:
    """Metrics service counts open tickets and detects overdue ones from raw due_by."""
    now = datetime.now(timezone.utc)
    overdue_due_by = (now - __import__('datetime').timedelta(days=1)).isoformat()

    ticket_service = MagicMock()
    ticket_service.list_tickets = AsyncMock(
        return_value=TicketListResponse(
                items=[
                    _build_ticket("open"),
                    _build_ticket("closed"),
                    _build_ticket("open", due_by=overdue_due_by),
                ],
            source="mock",
            cached=False,
        )
    )

    clickup_service = MagicMock()
    clickup_service.list_tasks = AsyncMock(return_value=[])
    clickup_service.get_week_time_entries = AsyncMock(
        return_value=WeekTimeResponse(
            source="mock",
            week_start=date.today(),
            week_end=date.today(),
            total_hours=0,
            entries=[],
        )
    )

    action_repository = MagicMock()
    action_repository.count_pending = AsyncMock(return_value=3)

    service = MetricsService(ticket_service, clickup_service, action_repository)
    metrics = await service.get_dashboard_metrics()

    assert metrics.tickets["open"] == 2
    assert metrics.tickets["overdue"] == 1
    assert metrics.tickets["pending_development"] == 0
    assert metrics.actions["pending_approval"] == 3


@pytest.mark.asyncio
async def test_should_detect_pending_development_tickets() -> None:
    """Tickets with development-related status or tags are counted as pending development."""
    ticket_service = MagicMock()
    ticket_service.list_tickets = AsyncMock(
        return_value=TicketListResponse(
                items=[
                    _build_ticket("open", tags=["development"]),
                    _build_ticket("open", tags=["development", "backend"]),
                    _build_ticket("open", tags=["other"]),
                ],
            source="mock",
            cached=False,
        )
    )

    clickup_service = MagicMock()
    clickup_service.list_tasks = AsyncMock(return_value=[])
    clickup_service.get_week_time_entries = AsyncMock(
        return_value=WeekTimeResponse(
            source="mock",
            week_start=date.today(),
            week_end=date.today(),
            total_hours=0,
            entries=[],
        )
    )

    action_repository = MagicMock()
    action_repository.count_pending = AsyncMock(return_value=0)

    service = MetricsService(ticket_service, clickup_service, action_repository)
    metrics = await service.get_dashboard_metrics()

    assert metrics.tickets["pending_development"] == 2


@pytest.mark.asyncio
async def test_should_categorize_clickup_tasks() -> None:
    """ClickUp tasks are categorized into pending, in progress, blocked and sprint."""
    ticket_service = MagicMock()
    ticket_service.list_tickets = AsyncMock(
        return_value=TicketListResponse(items=[], source="mock", cached=False)
    )

    clickup_service = MagicMock()
    clickup_service.list_tasks = AsyncMock(
        return_value=[
            ClickUpTask(id="1", name="A", status="open"),
            ClickUpTask(id="2", name="B", status="in progress"),
            ClickUpTask(id="3", name="C", status="blocked"),
            ClickUpTask(id="4", name="D", status="done"),
        ]
    )
    clickup_service.get_week_time_entries = AsyncMock(
        return_value=WeekTimeResponse(
            source="mock",
            week_start=date.today(),
            week_end=date.today(),
            total_hours=10,
            entries=[TimeEntry(task_id="1", task_name="A", hours=10, date=date.today())],
        )
    )

    action_repository = MagicMock()
    action_repository.count_pending = AsyncMock(return_value=0)

    service = MetricsService(ticket_service, clickup_service, action_repository)
    metrics = await service.get_dashboard_metrics()

    assert metrics.tasks["pending"] == 1
    assert metrics.tasks["in_progress"] == 1
    assert metrics.tasks["blocked"] == 1
    assert metrics.tasks["in_sprint"] == 1
    assert metrics.time["week_hours"] == 10
    assert metrics.time["today_hours"] == 10
