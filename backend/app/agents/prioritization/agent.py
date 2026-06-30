"""Prioritization agent."""

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.assistant.schemas.recommendations import PrioritizedWorkPlan, TicketRecommendation
from app.core.events.base import DomainEvent
from app.core.memory.interface import MemoryConfig, MemoryFacade
from app.domain.assistant.events import TicketTriageCompleted, WorkPlanGenerated


class PrioritizationAgent(BaseAgent):
    """Agent that creates an ordered work plan from ticket recommendations.

    The agent can be used directly through `build_plan()` for synchronous chat
    responses or through `handle()` for event-driven flows.

    Parameters:
        memory_facade: Memory facade factory.

    Returns:
        Prioritization agent instance.
    """

    subscribed_events = [TicketTriageCompleted]
    produced_events = [WorkPlanGenerated]
    agent_id = "prioritization"

    def __init__(self, memory_facade: MemoryFacade) -> None:
        super().__init__(
            agent_id=self.agent_id,
            memory_config=MemoryConfig(long_term=True),
            memory_facade=memory_facade,
        )

    async def _handle(self, event: DomainEvent, context: AgentContext) -> AgentResult:
        if isinstance(event, TicketTriageCompleted):
            recommendations = [TicketRecommendation(**rec) for rec in event.recommendations]
            work_plan = self.build_plan(recommendations)
            return AgentResult(
                events=[
                    WorkPlanGenerated(
                        conversation_id=event.conversation_id,
                        work_plan=work_plan.model_dump(),
                        metadata=event.metadata,
                    )
                ],
                summary=f"Generated work plan with {len(work_plan.today_focus)} focus items",
            )
        return AgentResult(summary=f"{self.agent_id} ignored event {type(event).__name__}")

    def build_plan(self, recommendations: list[TicketRecommendation]) -> PrioritizedWorkPlan:
        """Build a prioritized work plan.

        Parameters:
            recommendations: Ticket recommendations to group.

        Returns:
            Prioritized work plan grouped by category.
        """
        action_now = self._sort_by_confidence([item for item in recommendations if item.category == "action_now"])
        backlog_candidates = self._sort_by_confidence([item for item in recommendations if item.category == "backlog_candidate"])
        blocked_items = self._sort_by_confidence([item for item in recommendations if item.category == "needs_more_info"])
        monitor_items = self._sort_by_confidence([item for item in recommendations if item.category in ("ignore_or_monitor", "already_in_backlog")])
        return PrioritizedWorkPlan(
            today_focus=action_now[:3],
            next_actions=[*action_now[3:], *backlog_candidates[:3]],
            backlog_candidates=backlog_candidates,
            blocked_items=blocked_items,
            not_worth_actioning=monitor_items,
        )

    def _sort_by_confidence(self, recommendations: list[TicketRecommendation]) -> list[TicketRecommendation]:
        """Sort recommendations by confidence and ticket ID."""
        return sorted(recommendations, key=lambda item: (-item.confidence, item.ticket_id))
