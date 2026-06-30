"""Ticket triage agent."""

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.assistant.schemas.recommendations import TicketRecommendation
from app.core.events.base import DomainEvent
from app.core.memory.interface import MemoryConfig, MemoryFacade
from app.domain.agent.events import TicketsReviewRequested
from app.domain.assistant.events import (
    AssistantMessageReceived,
    TicketTriageCompleted,
)
from app.domain.integration_link.value_objects import RelationType
from app.schemas.ticket import Ticket
from app.tools.base import ToolResult

HIGH_PRIORITY_VALUES = {"3", "4", "high", "urgent", "alta", "crítica", "critical"}
LOW_SIGNAL_STATUSES = {"closed", "resolved", "5", "6"}


class TicketTriageAgent(BaseAgent):
    """Agent that classifies tickets into operational recommendation buckets.

    The agent can be used directly through `analyze()` for synchronous chat
    responses or through `handle()` for event-driven scheduled reviews.

    Parameters:
        memory_facade: Memory facade factory.

    Returns:
        Ticket triage agent instance.
    """

    subscribed_events = [AssistantMessageReceived, TicketsReviewRequested]
    produced_events = [TicketTriageCompleted]
    agent_id = "ticket_triage"

    def __init__(self, memory_facade: MemoryFacade) -> None:
        super().__init__(
            agent_id=self.agent_id,
            memory_config=MemoryConfig(long_term=True),
            memory_facade=memory_facade,
        )

    async def _handle(self, event: DomainEvent, context: AgentContext) -> AgentResult:
        if isinstance(event, (AssistantMessageReceived, TicketsReviewRequested)):
            return await self._handle_ticket_review(event, context)
        return AgentResult(summary=f"{self.agent_id} ignored event {type(event).__name__}")

    async def _handle_ticket_review(
        self,
        event: DomainEvent,
        context: AgentContext,
    ) -> AgentResult:
        """Handle a ticket review request by listing tickets and triaging them."""
        fresh_tool = context.get_tool("freshservice")
        mongo_tool = context.get_tool("mongo")

        list_result: ToolResult = await fresh_tool.execute(operation="list", scope="mine")
        if not list_result.success or list_result.data is None:
            return AgentResult(summary="Failed to list tickets for triage")

        tickets: list[Ticket] = list_result.data.get("tickets", [])
        existing_backlog_ids = await self._load_linked_ticket_ids(mongo_tool, tickets)
        recommendations = self.analyze(tickets, existing_backlog_ids)

        conversation_id = getattr(event, "conversation_id", "")
        return AgentResult(
            events=[
                TicketTriageCompleted(
                    conversation_id=conversation_id,
                    recommendations=[rec.model_dump() for rec in recommendations],
                    metadata=event.metadata,
                )
            ],
            summary=f"Triaged {len(tickets)} tickets into {len(recommendations)} recommendations",
        )

    async def _load_linked_ticket_ids(
        self,
        mongo_tool,
        tickets: list[Ticket],
    ) -> set[str]:
        """Return IDs of tickets already linked to ClickUp tasks."""
        linked: set[str] = set()
        for ticket in tickets:
            result = await mongo_tool.execute(
                operation="find_link",
                source_system="freshservice",
                source_id=ticket.id,
                relation_type=RelationType.TICKET_TO_TASK,
            )
            if result.success and result.data is not None:
                linked.add(ticket.id)
        return linked

    def analyze(
        self,
        tickets: list[Ticket],
        existing_backlog_ticket_ids: set[str] | list[str],
    ) -> list[TicketRecommendation]:
        """Analyze tickets and build recommendations.

        Parameters:
            tickets: Tickets to classify.
            existing_backlog_ticket_ids: Fresh ticket IDs already linked to ClickUp.

        Returns:
            Recommendation list in the same order as input tickets.
        """
        existing_ids = set(existing_backlog_ticket_ids)
        return [self._recommend_ticket(ticket, existing_ids) for ticket in tickets]

    def _recommend_ticket(self, ticket: Ticket, existing_backlog_ticket_ids: set[str]) -> TicketRecommendation:
        """Build one ticket recommendation using deterministic rules."""
        if ticket.id in existing_backlog_ticket_ids:
            return TicketRecommendation(
                ticket_id=ticket.id,
                subject=ticket.subject,
                category="already_in_backlog",
                confidence=0.95,
                rationale="Este ticket ya tiene una tarea ClickUp vinculada, evitar duplicados es prioridad.",
                suggested_next_action="Revisar la tarea ClickUp existente en lugar de crear otra.",
            )

        if self._is_low_signal_status(ticket.status):
            return TicketRecommendation(
                ticket_id=ticket.id,
                subject=ticket.subject,
                category="ignore_or_monitor",
                confidence=0.8,
                rationale="El estado indica que el ticket ya está resuelto o cerrado.",
                suggested_next_action="Monitorizar solo si vuelve a abrirse o aparece nueva información.",
            )

        missing_information = self._missing_information(ticket)
        if missing_information:
            return TicketRecommendation(
                ticket_id=ticket.id,
                subject=ticket.subject,
                category="needs_more_info",
                confidence=0.7,
                rationale="No hay suficiente contexto para convertirlo responsablemente en backlog.",
                suggested_next_action="Pedir información antes de priorizar o crear tarea.",
                missing_information=missing_information,
            )

        if self._is_high_priority(ticket.priority):
            return TicketRecommendation(
                ticket_id=ticket.id,
                subject=ticket.subject,
                category="action_now",
                confidence=0.85,
                rationale="La prioridad del ticket es alta y tiene contexto suficiente para actuar.",
                suggested_next_action="Revisar hoy y decidir si requiere respuesta o tarea ClickUp.",
            )

        return TicketRecommendation(
            ticket_id=ticket.id,
            subject=ticket.subject,
            category="backlog_candidate",
            confidence=0.75,
            rationale="Tiene información suficiente, no parece cerrado y puede formalizarse como trabajo planificado.",
            suggested_next_action="Preparar una tarea ClickUp para revisión antes de crearla.",
        )

    def _is_high_priority(self, priority: str) -> bool:
        """Return whether a Fresh priority should be treated as high."""
        return priority.strip().lower() in HIGH_PRIORITY_VALUES

    def _is_low_signal_status(self, status: str) -> bool:
        """Return whether a Fresh status should be monitored instead of actioned."""
        return status.strip().lower() in LOW_SIGNAL_STATUSES

    def _missing_information(self, ticket: Ticket) -> list[str]:
        """Detect missing ticket information required for safe action."""
        missing: list[str] = []
        if not ticket.description or len(ticket.description.strip()) < 20:
            missing.append("Descripción clara del problema")
        if not ticket.requester.name or ticket.requester.name == "Unknown requester":
            missing.append("Solicitante identificado")
        return missing
