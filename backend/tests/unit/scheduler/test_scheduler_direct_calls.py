"""Tests for direct-call scheduler jobs (Pila A architecture).

These tests verify that:
- The Scheduler accepts async callables instead of an Orchestrator.
- configure_scheduler wires the correct number of jobs.
- The tickets-review job chains FreshserviceAgent → ClickUpAgent → FreshserviceAgent.
- The morning-summary job chains PlannerAgent → NotificationAgent.
- Jobs with no agent implementation (tasks, timesheet) log and return without error.
"""

import pytest

from app.agents.base import AgentContext, AgentResult
from app.domain.agent.events import (
    AgentCompleted,
    MorningSummaryGenerated,
    MorningSummaryRequested,
    TicketsReviewRequested,
)
from app.domain.task.events import TaskCreatedFromTicket
from app.domain.task.value_objects import TaskId
from app.domain.ticket.events import TicketWithoutTaskDetected
from app.domain.ticket.value_objects import TicketId
from app.infrastructure.scheduler.jobs import (
    _build_context,
    _make_morning_summary_job,
    _make_tasks_review_job,
    _make_tickets_review_job,
    _make_timesheet_review_job,
    configure_scheduler,
)
from app.infrastructure.scheduler.scheduler import Scheduler


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _RecordingAgent:
    """Fake agent that records calls and returns a fixed AgentResult."""

    def __init__(self, result: AgentResult) -> None:
        self.calls: list[object] = []
        self._result = result

    async def handle(self, event, context) -> AgentResult:
        self.calls.append(event)
        return self._result


class _FakeToolRegistry:
    """Returns an empty tool list."""

    def list_tools(self) -> list:
        return []


class _FakeContainer:
    """Minimal container that exposes recording agents and a tool registry."""

    def __init__(
        self,
        freshservice_agent=None,
        clickup_agent=None,
        planner_agent=None,
        notification_agent=None,
        clickup_status_sync_agent=None,
    ) -> None:
        self._freshservice = freshservice_agent or _RecordingAgent(AgentResult(events=[]))
        self._clickup = clickup_agent or _RecordingAgent(AgentResult(events=[]))
        self._planner = planner_agent or _RecordingAgent(AgentResult(events=[]))
        self._notification = notification_agent or _RecordingAgent(AgentResult(events=[]))
        self._clickup_status_sync = clickup_status_sync_agent or _RecordingAgent(AgentResult(events=[]))
        self._registry = _FakeToolRegistry()

    def freshservice_agent(self):
        return self._freshservice

    def clickup_agent(self):
        return self._clickup

    def planner_agent(self):
        return self._planner

    def notification_agent(self):
        return self._notification

    def clickup_status_sync_agent(self):
        return self._clickup_status_sync

    def tool_registry(self):
        return self._registry


# ---------------------------------------------------------------------------
# Scheduler unit tests
# ---------------------------------------------------------------------------


def test_scheduler_add_job_stores_callable():
    """add_job should store the callable for later registration."""
    scheduler = Scheduler()
    calls: list[str] = []

    async def my_job() -> None:
        calls.append("ran")

    scheduler.add_job("my-job", "*/5 * * * *", my_job)
    assert len(scheduler._jobs) == 1
    name, cron, func = scheduler._jobs[0]
    assert name == "my-job"
    assert func is my_job


@pytest.mark.asyncio
async def test_scheduler_run_job_calls_func():
    """_run_job should invoke the registered callable."""
    scheduler = Scheduler()
    invocations: list[str] = []

    async def my_job() -> None:
        invocations.append("ran")

    await scheduler._run_job("my-job", my_job)
    assert invocations == ["ran"]


@pytest.mark.asyncio
async def test_scheduler_run_job_catches_exceptions():
    """_run_job should catch and log exceptions without propagating."""

    async def failing_job() -> None:
        raise RuntimeError("boom")

    scheduler = Scheduler()
    # Should not raise.
    await scheduler._run_job("failing-job", failing_job)


# ---------------------------------------------------------------------------
# configure_scheduler
# ---------------------------------------------------------------------------


def test_configure_scheduler_registers_expected_jobs():
    """configure_scheduler should register the expected named jobs."""
    scheduler = Scheduler()
    container = _FakeContainer()
    configure_scheduler(scheduler, container)
    names = [name for name, _, _ in scheduler._jobs]
    assert "review-tickets-every-5m" in names
    assert "review-tasks-every-10m" in names
    assert "review-timesheet-18h" in names
    assert "morning-summary-09h" in names
    # At least the four core jobs must be present; additional jobs are allowed.
    assert len(names) >= 4


# ---------------------------------------------------------------------------
# Tickets review job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tickets_review_job_no_unlinked_tickets():
    """When FreshserviceAgent returns no TicketWithoutTaskDetected, ClickUpAgent is not called."""
    fresh = _RecordingAgent(
        AgentResult(
            events=[
                AgentCompleted(
                    agent_id="freshservice",
                    event_type="TicketsReviewRequested",
                    result_summary="No unlinked tickets",
                )
            ]
        )
    )
    clickup = _RecordingAgent(AgentResult(events=[]))
    container = _FakeContainer(freshservice_agent=fresh, clickup_agent=clickup)

    job = _make_tickets_review_job(container)
    await job()

    assert len(fresh.calls) == 1
    assert isinstance(fresh.calls[0], TicketsReviewRequested)
    assert len(clickup.calls) == 0


@pytest.mark.asyncio
async def test_tickets_review_job_chains_to_clickup_agent():
    """TicketWithoutTaskDetected events produced by Freshservice are passed to ClickUpAgent."""
    ticket_event = TicketWithoutTaskDetected(
        ticket_id=TicketId("42"),
        subject="Test ticket",
        reason="No task linked",
    )
    fresh = _RecordingAgent(AgentResult(events=[ticket_event]))
    clickup = _RecordingAgent(AgentResult(events=[]))
    container = _FakeContainer(freshservice_agent=fresh, clickup_agent=clickup)

    job = _make_tickets_review_job(container)
    await job()

    assert len(clickup.calls) == 1
    assert clickup.calls[0] is ticket_event


@pytest.mark.asyncio
async def test_tickets_review_job_chains_task_created_back_to_freshservice():
    """TaskCreatedFromTicket produced by ClickUpAgent is forwarded to FreshserviceAgent."""
    ticket_event = TicketWithoutTaskDetected(
        ticket_id=TicketId("42"),
        subject="Test ticket",
        reason="No task linked",
    )
    task_event = TaskCreatedFromTicket(
        task_id=TaskId("cu-99"),
        ticket_id=TicketId("42"),
        title="Test ticket",
        url="https://clickup.com/t/cu-99",
    )
    fresh = _RecordingAgent(AgentResult(events=[ticket_event]))
    clickup = _RecordingAgent(AgentResult(events=[task_event]))
    container = _FakeContainer(freshservice_agent=fresh, clickup_agent=clickup)

    job = _make_tickets_review_job(container)
    await job()

    # FreshserviceAgent should be called twice: once for TicketsReviewRequested,
    # once for TaskCreatedFromTicket.
    assert len(fresh.calls) == 2
    assert isinstance(fresh.calls[0], TicketsReviewRequested)
    assert fresh.calls[1] is task_event


@pytest.mark.asyncio
async def test_tickets_review_job_handles_multiple_unlinked_tickets():
    """Each TicketWithoutTaskDetected triggers a separate ClickUpAgent call."""
    events = [
        TicketWithoutTaskDetected(
            ticket_id=TicketId(str(i)),
            subject=f"Ticket {i}",
            reason="No task",
        )
        for i in range(3)
    ]
    fresh = _RecordingAgent(AgentResult(events=events))
    clickup = _RecordingAgent(AgentResult(events=[]))
    container = _FakeContainer(freshservice_agent=fresh, clickup_agent=clickup)

    job = _make_tickets_review_job(container)
    await job()

    assert len(clickup.calls) == 3


# ---------------------------------------------------------------------------
# Morning summary job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_morning_summary_job_chains_to_notification_agent():
    """MorningSummaryGenerated produced by PlannerAgent is forwarded to NotificationAgent."""
    summary_event = MorningSummaryGenerated(
        summary="All good today",
        plan=["Do thing A", "Do thing B"],
    )
    planner = _RecordingAgent(AgentResult(events=[summary_event]))
    notification = _RecordingAgent(AgentResult(events=[]))
    container = _FakeContainer(planner_agent=planner, notification_agent=notification)

    job = _make_morning_summary_job(container)
    await job()

    assert len(planner.calls) == 1
    assert isinstance(planner.calls[0], MorningSummaryRequested)
    assert len(notification.calls) == 1
    assert notification.calls[0] is summary_event


@pytest.mark.asyncio
async def test_morning_summary_job_no_summary_skips_notification():
    """When PlannerAgent emits no MorningSummaryGenerated, NotificationAgent is not called."""
    planner = _RecordingAgent(AgentResult(events=[]))
    notification = _RecordingAgent(AgentResult(events=[]))
    container = _FakeContainer(planner_agent=planner, notification_agent=notification)

    job = _make_morning_summary_job(container)
    await job()

    assert len(planner.calls) == 1
    assert len(notification.calls) == 0


# ---------------------------------------------------------------------------
# No-op stub jobs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tasks_review_job_runs_without_error():
    """tasks review job should run as a no-op without raising."""
    container = _FakeContainer()
    job = _make_tasks_review_job(container)
    await job()  # Should not raise.


@pytest.mark.asyncio
async def test_timesheet_review_job_runs_without_error():
    """timesheet review job should run as a no-op without raising."""
    container = _FakeContainer()
    job = _make_timesheet_review_job(container)
    await job()  # Should not raise.


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------


def test_build_context_returns_agent_context_with_tools():
    """_build_context should return an AgentContext populated with the registry's tools."""
    container = _FakeContainer()
    context = _build_context(container)
    assert isinstance(context, AgentContext)
    assert context.tools == []
