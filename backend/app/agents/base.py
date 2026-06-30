"""Base agent abstraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from app.core.events.base import DomainEvent
from app.core.memory.interface import AgentMemory, MemoryConfig
from app.core.memory.interface import MemoryFacade
from app.tools.base import ToolInterface


@dataclass
class AgentContext:
    """Context provided to an agent when handling an event.

    Parameters:
        workflow_id: Unique identifier for the current workflow execution.
        conversation_id: Optional conversation identifier for chat flows.
        correlation_id: Correlation ID shared across all events in a workflow.
        tools: Tools available to the agent.
        memory: Memory API scoped to the agent.
        data: Shared key-value data from other agents in the workflow.

    Returns:
        Agent context instance.
    """

    workflow_id: UUID = field(default_factory=uuid4)
    conversation_id: str | None = None
    correlation_id: UUID = field(default_factory=uuid4)
    tools: list[ToolInterface] = field(default_factory=list)
    memory: AgentMemory | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def get_tool(self, name: str) -> ToolInterface:
        """Return a tool by name.

        Parameters:
            name: Tool name.

        Returns:
            Tool instance.

        Edge cases:
            Raises KeyError if the tool is not available.
        """
        for tool in self.tools:
            if tool.name == name:
                return tool
        raise KeyError(f"Tool '{name}' is not available to this agent")


@dataclass
class AgentResult:
    """Result returned by an agent after handling an event.

    Parameters:
        events: Domain events produced by the agent.
        summary: Human-readable summary of what the agent did.
        requires_approval: Whether a produced action needs human approval.

    Returns:
        Agent result instance.
    """

    events: list[DomainEvent] = field(default_factory=list)
    summary: str = ""
    requires_approval: bool = False


class BaseAgent(ABC):
    """Base class for all specialized agents.

    Agents are autonomous units that consume domain events, use tools, read
    and write memory, and produce new domain events. They never call other
    agents directly.

    Parameters:
        agent_id: Unique agent identifier.
        memory_config: Memory layers this agent uses.
        memory_facade: Factory for agent-scoped memory.

    Returns:
        Base agent instance.
    """

    subscribed_events: list[type[DomainEvent]] = []
    produced_events: list[type[DomainEvent]] = []

    def __init__(
        self,
        agent_id: str,
        memory_config: MemoryConfig,
        memory_facade: MemoryFacade,
    ) -> None:
        self.agent_id = agent_id
        self._memory_config = memory_config
        self._memory_facade = memory_facade

    async def handle(self, event: DomainEvent, context: AgentContext) -> AgentResult:
        """Handle a domain event.

        Parameters:
            event: Domain event to handle.
            context: Agent context with tools, memory and shared data.

        Returns:
            Agent result with produced events and summary.

        Edge cases:
            Exceptions are caught and returned as AgentFailed events.
        """
        context.memory = self._memory_facade.for_agent(self.agent_id)
        try:
            return await self._handle(event, context)
        except Exception as exc:  # noqa: BLE001
            from app.domain.agent.events import AgentFailed

            return AgentResult(
                events=[
                    AgentFailed(
                        agent_id=self.agent_id,
                        event_type=type(event).__name__,
                        error=str(exc),
                        metadata=event.metadata,
                    )
                ],
                summary=f"{self.agent_id} failed: {exc}",
            )

    @abstractmethod
    async def _handle(self, event: DomainEvent, context: AgentContext) -> AgentResult:
        """Concrete handling logic implemented by subclasses."""

    def _event_with_source(self, event: DomainEvent, source: str) -> DomainEvent:
        """Copy an event with updated source metadata."""
        new_metadata = event.metadata
        return event.with_causation(event, source=source)
