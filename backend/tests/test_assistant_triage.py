"""Tests for the migrated ticket triage and prioritization agents.

These tests used to import the legacy app.assistant.agents modules.
They now exercise the migrated app.agents.triage and app.agents.prioritization agents.
"""

import pytest

from app.agents.prioritization.agent import PrioritizationAgent
from app.agents.triage.agent import TicketTriageAgent
from app.assistant.safety_policy import AssistantSafetyPolicy
from app.assistant.schemas.actions import AssistantAction
from app.assistant.schemas.context import AssistantContext
from app.schemas.clickup import WeekTimeResponse
from app.schemas.ticket import Ticket, TicketRequester


def make_ticket(ticket_id: str, priority: str = "medium", status: str = "open", description: str | None = "User cannot complete checkout after payment redirect.") -> Ticket:
    """Create a normalized ticket for assistant tests.

    Parameters:
        ticket_id: Fresh ticket identifier.
        priority: Ticket priority value.
        status: Ticket status value.
        description: Optional ticket description.

    Returns:
        Ticket test fixture.

    Edge cases:
        None description is allowed to test missing information classification.
    """
    return Ticket(
        id=ticket_id,
        subject=f"Ticket {ticket_id}",
        status=status,
        priority=priority,
        requester=TicketRequester(name="Ada Lovelace", email="ada@example.com"),
        description=description,
        raw={},
    )


def make_context(tickets: list[Ticket], existing_backlog_ticket_ids: list[str] | None = None) -> AssistantContext:
    """Create an assistant context for tests.

    Parameters:
        tickets: Tickets visible to the assistant.
        existing_backlog_ticket_ids: Fresh IDs already linked to ClickUp.

    Returns:
        Assistant context fixture.

    Edge cases:
        Missing existing backlog IDs defaults to an empty list.
    """
    return AssistantContext(
        tickets=tickets,
        ticket_source="fresh",
        week_time=WeekTimeResponse(source="clickup", week_start="2026-06-22", week_end="2026-06-28", total_hours=12.5, entries=[]),
        existing_backlog_ticket_ids=existing_backlog_ticket_ids or [],
    )


def test_should_classify_high_priority_ticket_as_action_now() -> None:
    """Verify high-priority tickets become immediate action recommendations."""
    agent = TicketTriageAgent.__new__(TicketTriageAgent)
    context = make_context([make_ticket("1001", priority="urgent")])

    recommendations = agent.analyze(context.tickets, context.existing_backlog_ticket_ids)

    assert recommendations[0].category == "action_now"
    assert recommendations[0].ticket_id == "1001"


def test_should_require_more_info_when_ticket_description_is_missing() -> None:
    """Verify tickets without useful description are blocked before backlog creation."""
    agent = TicketTriageAgent.__new__(TicketTriageAgent)
    context = make_context([make_ticket("1002", description="help")])

    recommendations = agent.analyze(context.tickets, context.existing_backlog_ticket_ids)

    assert recommendations[0].category == "needs_more_info"
    assert "Descripción clara del problema" in recommendations[0].missing_information


def test_should_not_propose_backlog_for_existing_clickup_link() -> None:
    """Verify already-linked tickets are protected from duplicate backlog creation."""
    agent = TicketTriageAgent.__new__(TicketTriageAgent)
    context = make_context([make_ticket("1003", priority="urgent")], existing_backlog_ticket_ids=["1003"])

    recommendations = agent.analyze(context.tickets, context.existing_backlog_ticket_ids)

    assert recommendations[0].category == "already_in_backlog"


def test_should_build_work_plan_from_recommendations() -> None:
    """Verify prioritization agent groups recommendations into a work plan."""
    triage = TicketTriageAgent.__new__(TicketTriageAgent)
    prioritization = PrioritizationAgent.__new__(PrioritizationAgent)
    context = make_context([make_ticket("1004")])

    recommendations = triage.analyze(context.tickets, context.existing_backlog_ticket_ids)
    work_plan = prioritization.build_plan(recommendations)

    assert len(work_plan.backlog_candidates) == 1
    assert work_plan.backlog_candidates[0].ticket_id == "1004"


def test_should_reject_execution_when_action_is_not_proposed() -> None:
    """Verify safety policy prevents replaying completed actions."""
    policy = AssistantSafetyPolicy()
    action = AssistantAction(
        id="action-1",
        action_type="prepare_clickup_task",
        status="completed",
        title="Prepare task",
        description="Already done",
        ticket_id="1005",
        requires_approval=True,
    )

    with pytest.raises(ValueError, match="Only proposed actions"):
        policy.ensure_can_execute(action)
