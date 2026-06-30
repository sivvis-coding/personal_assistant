"""Main orchestrator implementation."""

from uuid import UUID

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.events.base import DomainEvent
from app.core.events.bus import EventBus
from app.core.logging.logger import logger
from app.core.memory.interface import MemoryFacade
from app.orchestrator.context_manager import ContextManager, SharedContext
from app.orchestrator.router import EventRouter
from app.tools.base import ToolInterface


class Orchestrator:
    """Central coordinator for all agent execution.

    The orchestrator does not contain business logic. It routes events to
    agents, manages shared context, and publishes events produced by agents.

    Parameters:
        event_bus: Event bus used to publish events.
        router: Event router mapping events to agents.
        context_manager: Manager for shared workflow contexts.
        tools: Tools available to all agents.
        memory_facade: Factory for agent-scoped memory.

    Returns:
        Orchestrator instance.

    Edge cases:
        Events with no registered agents are logged and ignored.
        Agent failures do not stop other agents from handling the same event.
    """

    def __init__(
        self,
        event_bus: EventBus,
        router: EventRouter,
        context_manager: ContextManager,
        tools: list[ToolInterface],
        memory_facade: MemoryFacade,
    ) -> None:
        self._event_bus = event_bus
        self._router = router
        self._context_manager = context_manager
        self._tools = tools
        self._memory_facade = memory_facade

    async def handle(self, event: DomainEvent) -> list[AgentResult]:
        """Handle a domain event by routing it to the appropriate agents.

        Parameters:
            event: Domain event to handle.

        Returns:
            List of agent results.
        """
        agents = self._router.resolve(event)
        if not agents:
            logger.warning(
                "No agents registered for event",
                extra={"event_type": type(event).__name__, "event_id": str(event.event_id)},
            )
            return []

        context = self._context_manager.create(event)
        results: list[AgentResult] = []

        for agent in agents:
            agent_context = self._build_agent_context(context)
            result = await agent.handle(event, agent_context)
            results.append(result)
            context.events_produced.extend(result.events)

            for produced_event in result.events:
                await self._event_bus.publish(produced_event)

        return results

    async def start_workflow(self, event: DomainEvent) -> list[AgentResult]:
        """Start a new workflow from an event.

        This is the preferred entry point for scheduled jobs and API calls.
        """
        return await self.handle(event)

    def _build_agent_context(self, shared_context: SharedContext) -> AgentContext:
        """Build an agent context from a shared workflow context."""
        return AgentContext(
            workflow_id=shared_context.workflow_id,
            correlation_id=shared_context.correlation_id,
            tools=self._tools,
            memory=self._memory_facade.for_agent("orchestrator"),
            data=shared_context.data,
        )
