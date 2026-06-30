"""ClickUp agent."""

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.events.base import DomainEvent
from app.core.memory.interface import MemoryConfig, MemoryFacade
from app.domain.agent.events import AgentCompleted
from app.domain.task.events import TaskCreatedFromTicket
from app.domain.task.value_objects import TaskId
from app.domain.ticket.events import TicketUpdatedWithTaskLink, TicketWithoutTaskDetected
from app.tools.base import ToolResult


class ClickUpAgent(BaseAgent):
    """Agent responsible for ClickUp task operations.

    Parameters:
        memory_facade: Memory facade factory.

    Returns:
        ClickUp agent instance.
    """

    subscribed_events = [TicketWithoutTaskDetected]
    produced_events = [TaskCreatedFromTicket, TicketUpdatedWithTaskLink]
    agent_id = "clickup"

    def __init__(self, memory_facade: MemoryFacade) -> None:
        super().__init__(
            agent_id=self.agent_id,
            memory_config=MemoryConfig(long_term=True),
            memory_facade=memory_facade,
        )

    async def _handle(self, event: DomainEvent, context: AgentContext) -> AgentResult:
        if isinstance(event, TicketWithoutTaskDetected):
            return await self._handle_ticket_without_task(context, event)
        return AgentResult(summary=f"{self.agent_id} ignored event {type(event).__name__}")

    async def _handle_ticket_without_task(
        self,
        context: AgentContext,
        event: TicketWithoutTaskDetected,
    ) -> AgentResult:
        """Create an audited, idempotent ClickUp task from a Freshservice ticket.

        Routes through TicketToClickUpTool so all task creation is audited via
        WorkflowRunRepository and deduplicated via IntegrationLinkRepository.
        """
        ticket_to_clickup_tool = context.get_tool("ticket_to_clickup")
        ticket_id = event.ticket_id.value

        prepare_result: ToolResult = await ticket_to_clickup_tool.execute(
            operation="prepare",
            ticket_id=ticket_id,
        )
        if not prepare_result.success or prepare_result.data is None:
            return AgentResult(summary=f"Failed to prepare ClickUp task proposal for ticket {ticket_id}")

        user_story = prepare_result.data.get("user_story")

        approve_result: ToolResult = await ticket_to_clickup_tool.execute(
            operation="approve",
            ticket_id=ticket_id,
            user_story=user_story,
        )
        if not approve_result.success or approve_result.data is None:
            return AgentResult(summary=f"Failed to create ClickUp task for ticket {ticket_id}")

        clickup_task = approve_result.data.get("clickup_task", {})
        task_id = str(clickup_task.get("id", ""))
        task_url = clickup_task.get("url")

        return AgentResult(
            events=[
                TaskCreatedFromTicket(
                    task_id=TaskId(task_id),
                    ticket_id=event.ticket_id,
                    title=event.subject,
                    url=task_url,
                    metadata=event.metadata,
                ),
                AgentCompleted(
                    agent_id=self.agent_id,
                    event_type=type(event).__name__,
                    result_summary=f"Created ClickUp task {task_id} for ticket {ticket_id}",
                    metadata=event.metadata,
                ),
            ],
            summary=f"Created ClickUp task {task_id} for ticket {ticket_id}",
        )
