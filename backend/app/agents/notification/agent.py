"""Notification agent."""

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.events.base import DomainEvent
from app.core.memory.interface import MemoryConfig, MemoryFacade
from app.domain.agent.events import AgentCompleted
from app.domain.timesheet.events import TimesheetMissing
from app.domain.agent.events import MorningSummaryGenerated


class NotificationAgent(BaseAgent):
    """Agent responsible for delivering notifications to the user.

    Phase 1 stores notifications as long-term memory. Future phases will
    deliver to Slack, Teams, email, etc.

    Parameters:
        memory_facade: Memory facade factory.

    Returns:
        Notification agent instance.
    """

    subscribed_events = [MorningSummaryGenerated, TimesheetMissing]
    produced_events = []
    agent_id = "notification"

    def __init__(self, memory_facade: MemoryFacade) -> None:
        super().__init__(
            agent_id=self.agent_id,
            memory_config=MemoryConfig(long_term=True),
            memory_facade=memory_facade,
        )

    async def _handle(self, event: DomainEvent, context: AgentContext) -> AgentResult:
        if isinstance(event, MorningSummaryGenerated):
            return await self._handle_morning_summary(event, context)
        if isinstance(event, TimesheetMissing):
            return await self._handle_timesheet_missing(event, context)
        return AgentResult(summary=f"{self.agent_id} ignored event {type(event).__name__}")

    async def _handle_morning_summary(
        self,
        event: MorningSummaryGenerated,
        context: AgentContext,
    ) -> AgentResult:
        """Persist a morning summary notification."""
        if context.memory is not None:
            await context.memory.store_long(
                key=f"notification:{event.event_id}",
                value={
                    "type": "morning_summary",
                    "summary": event.summary,
                    "plan": event.plan,
                },
                metadata={"agent_id": self.agent_id},
            )

        return AgentResult(
            events=[
                AgentCompleted(
                    agent_id=self.agent_id,
                    event_type=type(event).__name__,
                    result_summary="Stored morning summary notification",
                    metadata=event.metadata,
                )
            ],
            summary=event.summary,
        )

    async def _handle_timesheet_missing(
        self,
        event: TimesheetMissing,
        context: AgentContext,
    ) -> AgentResult:
        """Persist a timesheet missing notification."""
        message = (
            f"Timesheet missing {event.missing_hours}h for {event.missing_date.isoformat()}. "
            f"Suggestions: {', '.join(event.suggestions) or 'none'}"
        )
        if context.memory is not None:
            await context.memory.store_long(
                key=f"notification:{event.event_id}",
                value={
                    "type": "timesheet_missing",
                    "message": message,
                },
                metadata={"agent_id": self.agent_id},
            )

        return AgentResult(
            events=[
                AgentCompleted(
                    agent_id=self.agent_id,
                    event_type=type(event).__name__,
                    result_summary="Stored timesheet missing notification",
                    metadata=event.metadata,
                )
            ],
            summary=message,
        )
