"""ClickUp status sync agent."""

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.events.base import DomainEvent
from app.core.memory.interface import MemoryConfig, MemoryFacade
from app.domain.agent.events import AgentCompleted
from app.domain.task.events import ClickUpStatusSyncRequested
from app.services.clickup_status_sync_service import ClickUpStatusSyncService


class ClickUpStatusSyncAgent(BaseAgent):
    """Agent that delegates ClickUp-to-Freshservice status synchronisation.

    This agent is a thin scheduler adapter: it responds to the periodic
    ``ClickUpStatusSyncRequested`` event by calling
    ``ClickUpStatusSyncService.sync_all()`` and returning a summary.

    All business logic lives in the service so it can also be called
    directly from the ``/api/v1/sync/clickup-status`` endpoint without
    going through the event bus.

    Parameters:
        memory_facade: Memory facade factory (required by BaseAgent).
        sync_service: Service that performs the actual status sync.

    Returns:
        ClickUp status sync agent instance.
    """

    subscribed_events = [ClickUpStatusSyncRequested]
    produced_events = []
    agent_id = "clickup_status_sync"

    def __init__(
        self,
        memory_facade: MemoryFacade,
        sync_service: ClickUpStatusSyncService,
    ) -> None:
        super().__init__(
            agent_id=self.agent_id,
            memory_config=MemoryConfig(),
            memory_facade=memory_facade,
        )
        self._sync_service = sync_service

    async def _handle(self, event: DomainEvent, context: AgentContext) -> AgentResult:
        if isinstance(event, ClickUpStatusSyncRequested):
            return await self._handle_sync_requested(event)
        return AgentResult(summary=f"{self.agent_id} ignored event {type(event).__name__}")

    async def _handle_sync_requested(self, event: ClickUpStatusSyncRequested) -> AgentResult:
        """Run the status sync and emit a completion event.

        Parameters:
            event: The scheduler-fired sync request event.

        Returns:
            Agent result with a summary of sync outcomes.

        Edge cases:
            Per-link errors are handled inside the service; this handler
            only fails if the entire service call raises.
        """
        results = await self._sync_service.sync_all()

        noted = sum(1 for r in results if r.get("action") == "noted")
        unchanged = sum(1 for r in results if r.get("action") == "unchanged")
        errors = sum(1 for r in results if r.get("action") == "error")

        summary = (
            f"ClickUp status sync complete: {noted} noted, "
            f"{unchanged} unchanged, {errors} error(s) across {len(results)} link(s)"
        )

        return AgentResult(
            events=[
                AgentCompleted(
                    agent_id=self.agent_id,
                    event_type=type(event).__name__,
                    result_summary=summary,
                    metadata=event.metadata,
                )
            ],
            summary=summary,
        )
