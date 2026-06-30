"""Planner agent."""

from pathlib import Path
from typing import Any

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.planner.schemas import MorningSummaryResponse
from app.core.events.base import DomainEvent
from app.core.llm.provider import LLMProvider
from app.core.memory.interface import MemoryConfig, MemoryFacade
from app.domain.agent.events import AgentCompleted, MorningSummaryGenerated, MorningSummaryRequested
from app.tools.base import ToolResult


def _load_prompt(prompt_file: str) -> str:
    """Load a versioned prompt file from the planner prompts directory.

    Parameters:
        prompt_file: Prompt file name.

    Returns:
        Prompt text.

    Edge cases:
        Missing prompt file raises FileNotFoundError because deployment is invalid.
    """
    return (Path(__file__).resolve().parent / "prompts" / prompt_file).read_text(encoding="utf-8")


class PlannerAgent(BaseAgent):
    """Agent responsible for planning and summarization using an LLM.

    Parameters:
        memory_facade: Memory facade factory.
        llm_provider: LLM provider for generating summaries and plans.

    Returns:
        Planner agent instance.
    """

    subscribed_events = [MorningSummaryRequested]
    produced_events = [MorningSummaryGenerated]
    agent_id = "planner"

    def __init__(self, memory_facade: MemoryFacade, llm_provider: LLMProvider) -> None:
        super().__init__(
            agent_id=self.agent_id,
            memory_config=MemoryConfig(short_term=True, long_term=True, user_prefs=True),
            memory_facade=memory_facade,
        )
        self._llm_provider = llm_provider

    async def _handle(self, event: DomainEvent, context: AgentContext) -> AgentResult:
        if isinstance(event, MorningSummaryRequested):
            return await self._handle_morning_summary(context, event)
        return AgentResult(summary=f"{self.agent_id} ignored event {type(event).__name__}")

    async def _handle_morning_summary(
        self,
        context: AgentContext,
        event: MorningSummaryRequested,
    ) -> AgentResult:
        """Generate a morning summary from tickets and tasks using the LLM."""
        fresh_tool = context.get_tool("freshservice")
        clickup_tool = context.get_tool("clickup")

        ticket_result: ToolResult = await fresh_tool.execute(operation="list", scope="mine")
        task_result: ToolResult = await clickup_tool.execute(operation="list_tasks")

        tickets: list[dict[str, Any]] = []
        if ticket_result.success and ticket_result.data is not None:
            tickets = ticket_result.data.get("tickets", [])

        tasks: list[dict[str, Any]] = []
        if task_result.success and task_result.data is not None:
            tasks = task_result.data.get("tasks", [])

        llm_context = {
            "assigned_tickets": tickets,
            "active_tasks": tasks,
        }

        prompt = _load_prompt("morning_summary_v1.txt")
        response_data = await self._llm_provider.complete_structured(
            prompt=prompt,
            context=llm_context,
            schema=MorningSummaryResponse,
        )

        summary_response = MorningSummaryResponse.model_validate(response_data)

        return AgentResult(
            events=[
                MorningSummaryGenerated(
                    summary=summary_response.summary,
                    plan=summary_response.plan,
                    metadata=event.metadata,
                ),
                AgentCompleted(
                    agent_id=self.agent_id,
                    event_type=type(event).__name__,
                    result_summary=f"Generated morning summary with {len(summary_response.plan)} action(s)",
                    metadata=event.metadata,
                ),
            ],
            summary=summary_response.summary,
        )
