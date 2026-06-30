"""Event to agent router."""

from app.agents.base import BaseAgent
from app.core.events.base import DomainEvent


class EventRouter:
    """Maps domain events to agents.

    The router is intentionally simple in Phase 1: it maps each event type to
    one or more agents based on explicit subscriptions. A future LLM-based
    router can be added behind the same interface.
    """

    def __init__(self) -> None:
        """Initialize an empty router."""
        self._routes: dict[type[DomainEvent], list[BaseAgent]] = {}

    def register(self, event_type: type[DomainEvent], agent: BaseAgent) -> None:
        """Register an agent as a handler for an event type.

        Parameters:
            event_type: Domain event class.
            agent: Agent that handles the event.

        Returns:
            None.
        """
        self._routes.setdefault(event_type, []).append(agent)

    def resolve(self, event: DomainEvent) -> list[BaseAgent]:
        """Return the agents that should handle an event.

        Parameters:
            event: Domain event to route.

        Returns:
            List of agents subscribed to the event type.

        Edge cases:
            Events with no registered agents return an empty list.
        """
        return list(self._routes.get(type(event), []))
