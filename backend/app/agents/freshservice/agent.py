"""Freshservice agent."""

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.events.base import DomainEvent
from app.core.memory.interface import MemoryConfig, MemoryFacade
from app.domain.agent.events import AgentCompleted, TicketsReviewRequested
from app.domain.integration_link.value_objects import RelationType
from app.domain.task.events import TaskCreatedFromTicket
from app.domain.ticket.events import TicketUpdatedWithTaskLink, TicketWithoutTaskDetected
from app.domain.ticket.value_objects import TicketId
from app.tools.base import ToolResult


class FreshserviceAgent(BaseAgent):
    """Agent responsible for Freshservice ticket operations.

    Parameters:
        memory_facade: Memory facade factory.

    Returns:
        Freshservice agent instance.
    """

    subscribed_events = [TicketsReviewRequested, TaskCreatedFromTicket]
    produced_events = [TicketWithoutTaskDetected, TicketUpdatedWithTaskLink]
    agent_id = "freshservice"

    def __init__(self, memory_facade: MemoryFacade) -> None:
        super().__init__(
            agent_id=self.agent_id,
            memory_config=MemoryConfig(long_term=True, semantic=True),
            memory_facade=memory_facade,
        )

    async def _handle(self, event: DomainEvent, context: AgentContext) -> AgentResult:
        if isinstance(event, TicketsReviewRequested):
            return await self._handle_tickets_review(context, event)
        if isinstance(event, TaskCreatedFromTicket):
            return await self._handle_task_created(context, event)
        return AgentResult(summary=f"{self.agent_id} ignored event {type(event).__name__}")

    async def _handle_tickets_review(self, context: AgentContext, event: TicketsReviewRequested) -> AgentResult:
        """Review assigned tickets and detect those without linked tasks."""
        fresh_tool = context.get_tool("freshservice")
        mongo_tool = context.get_tool("mongo")

        result: ToolResult = await fresh_tool.execute(operation="list", scope="mine")
        if not result.success or result.data is None:
            return AgentResult(summary="Failed to list tickets", events=[])

        tickets = result.data.get("tickets", [])
        produced_events: list[DomainEvent] = []
        unlinked_count = 0

        for ticket in tickets:
            if ticket.status.lower() in ("resolved", "closed"):
                continue

            link_result = await mongo_tool.execute(
                operation="find_link",
                source_system="freshservice",
                source_id=ticket.id,
                relation_type=RelationType.TICKET_TO_TASK,
            )
            if link_result.success and link_result.data is not None:
                continue

            produced_events.append(
                TicketWithoutTaskDetected(
                    ticket_id=TicketId(ticket.id),
                    subject=ticket.subject,
                    reason="No ClickUp task linked",
                    metadata=event.metadata,
                )
            )
            unlinked_count += 1

        if unlinked_count == 0:
            return AgentResult(
                summary="All open tickets already have linked ClickUp tasks",
                events=[
                    AgentCompleted(
                        agent_id=self.agent_id,
                        event_type=type(event).__name__,
                        result_summary="No unlinked tickets found",
                        metadata=event.metadata,
                    )
                ],
            )

        return AgentResult(
            events=produced_events,
            summary=f"Detected {unlinked_count} ticket(s) without linked tasks",
        )

    async def _handle_task_created(self, context: AgentContext, event: TaskCreatedFromTicket) -> AgentResult:
        """Update the original ticket when a ClickUp task is created from it."""
        fresh_tool = context.get_tool("freshservice")
        note = f"ClickUp task created: {event.url}"

        result = await fresh_tool.execute(
            operation="update",
            ticket_id=event.ticket_id.value,
            changes={"note": note},
        )

        if not result.success:
            return AgentResult(summary=f"Failed to update ticket {event.ticket_id.value}")

        return AgentResult(
            events=[
                TicketUpdatedWithTaskLink(
                    ticket_id=event.ticket_id,
                    task_id=event.task_id.value,
                    note=note,
                    metadata=event.metadata,
                )
            ],
            summary=f"Updated ticket {event.ticket_id.value} with ClickUp link",
        )
