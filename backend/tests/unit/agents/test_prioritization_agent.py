"""Tests for the migrated prioritization agent."""

import pytest

from app.agents.base import AgentContext
from app.agents.prioritization.agent import PrioritizationAgent
from app.assistant.schemas.recommendations import TicketRecommendation
from app.domain.assistant.events import TicketTriageCompleted


class FakeMemoryFacade:
    """Memory facade returning a no-op AgentMemory."""

    def for_agent(self, agent_id: str):
        from app.core.memory.interface import AgentMemory, MemoryConfig

        return AgentMemory(
            agent_id=agent_id,
            config=MemoryConfig(),
            short_term=None,
            long_term=None,
            semantic=None,
            user_prefs=None,
        )


def test_build_plan_groups_recommendations():
    """The agent groups recommendations into a prioritized work plan."""
    agent = PrioritizationAgent(FakeMemoryFacade())
    recommendations = [
        TicketRecommendation(
            ticket_id="1",
            subject="High priority",
            category="action_now",
            confidence=0.9,
            rationale="Important",
            suggested_next_action="Act",
        ),
        TicketRecommendation(
            ticket_id="2",
            subject="Backlog candidate",
            category="backlog_candidate",
            confidence=0.75,
            rationale="Can wait",
            suggested_next_action="Prepare task",
        ),
        TicketRecommendation(
            ticket_id="3",
            subject="Missing info",
            category="needs_more_info",
            confidence=0.6,
            rationale="Need data",
            suggested_next_action="Ask",
        ),
    ]

    plan = agent.build_plan(recommendations)

    assert len(plan.today_focus) == 1
    assert plan.today_focus[0].ticket_id == "1"
    assert len(plan.backlog_candidates) == 1
    assert len(plan.blocked_items) == 1


@pytest.mark.asyncio
async def test_handle_emits_work_plan_generated_event():
    """The event handler emits WorkPlanGenerated from TicketTriageCompleted."""
    agent = PrioritizationAgent(FakeMemoryFacade())
    recommendations = [
        {
            "ticket_id": "1",
            "subject": "High priority",
            "category": "action_now",
            "confidence": 0.9,
            "rationale": "Important",
            "suggested_next_action": "Act",
        }
    ]
    context = AgentContext()

    result = await agent.handle(
        TicketTriageCompleted(conversation_id="conv-1", recommendations=recommendations),
        context,
    )

    assert len(result.events) == 1
    assert result.events[0].conversation_id == "conv-1"
    assert result.events[0].work_plan["today_focus"][0]["ticket_id"] == "1"
