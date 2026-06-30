from datetime import datetime, timezone

from app.repositories.assistant_action_repository import AssistantActionRepository
from app.schemas.metrics import DashboardMetrics
from app.services import sla as sla_module
from app.services.clickup_service import ClickUpService
from app.services.ticket_service import TicketService


class MetricsService:
    """Aggregate dashboard metrics from multiple services.

    Parameters:
        ticket_service: Service used to list tickets.
        clickup_service: Service used to read ClickUp data.
        action_repository: Repository used to count pending actions.

    Returns:
        Service that computes dashboard metrics.

    Edge cases:
        External service failures are propagated to the API layer.
    """

    def __init__(
        self,
        ticket_service: TicketService,
        clickup_service: ClickUpService,
        action_repository: AssistantActionRepository,
    ) -> None:
        """Initialize metrics service with its dependencies."""
        self._ticket_service = ticket_service
        self._clickup_service = clickup_service
        self._action_repository = action_repository

    async def get_dashboard_metrics(self) -> DashboardMetrics:
        """Compute and return dashboard metrics.

        Parameters:
            None.

        Returns:
            Dashboard metrics DTO.

        Edge cases:
            Metrics rely on heuristics when external systems do not provide explicit categories.
        """
        ticket_response = await self._ticket_service.list_tickets("mine")
        tickets = ticket_response.items

        now = datetime.now(timezone.utc)
        open_tickets = [ticket for ticket in tickets if not self._is_closed(ticket.status)]
        overdue_tickets = [
            ticket
            for ticket in open_tickets
            if self._is_overdue(ticket, now)
        ]
        pending_development_tickets = [
            ticket
            for ticket in open_tickets
            if self._is_pending_development(ticket)
        ]

        clickup_tasks = await self._clickup_service.list_tasks()
        pending_tasks = [task for task in clickup_tasks if self._is_pending_status(task.status)]
        in_progress_tasks = [task for task in clickup_tasks if self._is_in_progress_status(task.status)]
        blocked_tasks = [task for task in clickup_tasks if self._is_blocked_status(task.status)]
        in_sprint_tasks = [task for task in clickup_tasks if self._is_in_sprint(task)]

        week_time = await self._clickup_service.get_week_time_entries()
        pending_actions = await self._action_repository.count_pending()

        return DashboardMetrics(
            tickets={
                "open": len(open_tickets),
                "overdue": len(overdue_tickets),
                "pending_development": len(pending_development_tickets),
                "assigned_to_me": 0,  # TODO: derive from authenticated agent when available
            },
            tasks={
                "pending": len(pending_tasks),
                "in_progress": len(in_progress_tasks),
                "in_sprint": len(in_sprint_tasks),
                "blocked": len(blocked_tasks),
            },
            time={
                "today_hours": self._today_hours(week_time.entries),
                "week_hours": week_time.total_hours,
                "month_hours": 0,  # TODO: add monthly aggregation when needed
            },
            actions={
                "pending_approval": pending_actions,
            },
        )

    @staticmethod
    def _is_closed(status: str) -> bool:
        """Return whether a ticket status means the ticket is closed."""
        return status.lower() in {"closed", "resolved", "resolved_and_closed"}

    @staticmethod
    def _is_overdue(ticket, now: datetime) -> bool:
        """Return whether an open ticket is overdue based on raw due_by."""
        return sla_module.is_overdue(ticket, now)

    @staticmethod
    def _is_pending_development(ticket) -> bool:
        """Return whether a ticket is pending development based on status/tags."""
        status = ticket.status.lower()
        raw = ticket.raw or {}
        tags = {tag.lower() for tag in raw.get("tags", []) if isinstance(tag, str)}
        return (
            "development" in status
            or "desarrollo" in status
            or "pending development" in status
            or "development" in tags
            or "desarrollo" in tags
        )

    @staticmethod
    def _is_pending_status(status: str) -> bool:
        """Return whether a ClickUp task status means pending."""
        return status.lower() in {"open", "to do", "todo", "pending", "backlog"}

    @staticmethod
    def _is_in_progress_status(status: str) -> bool:
        """Return whether a ClickUp task status means in progress."""
        return status.lower() in {"in progress", "in_progress", "active"}

    @staticmethod
    def _is_blocked_status(status: str) -> bool:
        """Return whether a ClickUp task status means blocked."""
        return status.lower() in {"blocked", "on hold", "on_hold"}

    @staticmethod
    def _is_in_sprint(task) -> bool:
        """Return whether a ClickUp task belongs to a sprint.

        Edge cases:
            Without sprint metadata, tasks in progress are assumed to be in the active sprint.
        """
        # TODO: replace heuristic with real sprint membership when ClickUp sprint data is integrated
        return MetricsService._is_in_progress_status(task.status)

    @staticmethod
    def _today_hours(entries) -> float:
        """Sum hours reported for today."""
        today = datetime.now(timezone.utc).date()
        return sum(entry.hours for entry in entries if entry.date == today)
