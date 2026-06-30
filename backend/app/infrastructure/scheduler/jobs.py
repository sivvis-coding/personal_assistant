"""Default scheduler job definitions."""

from app.infrastructure.scheduler.scheduler import Scheduler


def configure_scheduler(scheduler: Scheduler, container) -> None:
    """Register default jobs on a scheduler instance using direct agent calls.

    Each job calls agent methods directly instead of routing through the
    Orchestrator/EventBus. The event chain for tickets is:

        FreshserviceAgent (TicketsReviewRequested)
          → ClickUpAgent (TicketWithoutTaskDetected) per unlinked ticket
            → FreshserviceAgent (TaskCreatedFromTicket) per created task

    The morning summary chain is:

        PlannerAgent (MorningSummaryRequested)
          → NotificationAgent (MorningSummaryGenerated)

    TasksReviewRequested and TimesheetReviewRequested have no agent
    implementations yet; their jobs are preserved as no-ops.

    Parameters:
        scheduler: Scheduler to configure.
        container: Configured DI container supplying agents and tools.

    Returns:
        None.
    """
    scheduler.add_job(
        "review-tickets-every-5m",
        "*/5 * * * *",
        _make_tickets_review_job(container),
    )
    scheduler.add_job(
        "review-tasks-every-10m",
        "*/10 * * * *",
        _make_tasks_review_job(container),
    )
    scheduler.add_job(
        "review-timesheet-18h",
        "0 18 * * *",
        _make_timesheet_review_job(container),
    )
    scheduler.add_job(
        "morning-summary-09h",
        "0 9 * * *",
        _make_morning_summary_job(container),
    )
    scheduler.add_job(
        "clickup-status-sync-every-15m",
        "*/15 * * * *",
        _make_clickup_status_sync_job(container),
    )


def _make_tickets_review_job(container):
    """Return the async callable for the tickets review job.

    Flow:
        FreshserviceAgent detects unlinked tickets, then for each
        TicketWithoutTaskDetected the ClickUpAgent creates a task, and for
        each TaskCreatedFromTicket the FreshserviceAgent updates the ticket.
    """
    from app.agents.base import AgentContext
    from app.domain.agent.events import TicketsReviewRequested
    from app.domain.task.events import TaskCreatedFromTicket
    from app.domain.ticket.events import TicketWithoutTaskDetected

    async def run() -> None:
        context = _build_context(container)
        fresh_agent = container.freshservice_agent()
        clickup_agent = container.clickup_agent()

        fresh_result = await fresh_agent.handle(TicketsReviewRequested(), context)

        for event in fresh_result.events:
            if not isinstance(event, TicketWithoutTaskDetected):
                continue
            cu_result = await clickup_agent.handle(event, context)
            for cu_event in cu_result.events:
                if isinstance(cu_event, TaskCreatedFromTicket):
                    await fresh_agent.handle(cu_event, context)

    return run


def _make_tasks_review_job(container):
    """Return the async callable for the tasks review job (no-op until implemented)."""

    async def run() -> None:
        from app.core.logging.logger import logger
        logger.info("tasks review job fired — no agent implemented yet")

    return run


def _make_timesheet_review_job(container):
    """Return the async callable for the timesheet review job (no-op until implemented)."""

    async def run() -> None:
        from app.core.logging.logger import logger
        logger.info("timesheet review job fired — no agent implemented yet")

    return run


def _make_morning_summary_job(container):
    """Return the async callable for the morning summary job.

    Flow:
        PlannerAgent generates the morning summary, then for each
        MorningSummaryGenerated the NotificationAgent stores it.
    """
    from app.domain.agent.events import MorningSummaryGenerated, MorningSummaryRequested

    async def run() -> None:
        context = _build_context(container)
        planner_agent = container.planner_agent()
        notification_agent = container.notification_agent()

        planner_result = await planner_agent.handle(MorningSummaryRequested(), context)

        for event in planner_result.events:
            if isinstance(event, MorningSummaryGenerated):
                await notification_agent.handle(event, context)

    return run


def _make_clickup_status_sync_job(container):
    """Return the async callable for the ClickUp status sync job.

    Flow:
        ClickUpStatusSyncService queries all ticket_to_task links, fetches
        current ClickUp task statuses, and posts a private Freshservice note
        for any link where the status changed since the last run.
    """
    from app.domain.task.events import ClickUpStatusSyncRequested

    async def run() -> None:
        context = _build_context(container)
        sync_agent = container.clickup_status_sync_agent()
        await sync_agent.handle(ClickUpStatusSyncRequested(), context)

    return run


def _build_context(container):
    """Build an AgentContext with all registered tools from the container.

    Parameters:
        container: Configured DI container.

    Returns:
        AgentContext populated with the tool registry's tools.
    """
    from app.agents.base import AgentContext

    tools = container.tool_registry().list_tools()
    return AgentContext(tools=tools)
