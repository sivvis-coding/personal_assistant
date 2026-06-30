"""Tests for the LLM-backed planner agent."""

import pytest

from app.agents.base import AgentContext
from app.agents.planner.agent import PlannerAgent
from app.core.llm.provider import LLMProvider
from app.core.memory.interface import AgentMemory, MemoryConfig
from app.domain.agent.events import MorningSummaryGenerated, MorningSummaryRequested
from app.tools.base import ToolInterface, ToolResult


class FakeMemoryFacade:
    """Memory facade returning a no-op AgentMemory."""

    def for_agent(self, agent_id: str) -> AgentMemory:
        return AgentMemory(
            agent_id=agent_id,
            config=MemoryConfig(),
            short_term=None,
            long_term=None,
            semantic=None,
            user_prefs=None,
        )


class FakeTool(ToolInterface):
    """Base fake tool with a configurable name and deterministic response."""

    _default_name = "fake_tool"
    description = "Fake tool"
    parameters = []

    def __init_subclass__(cls, tool_name: str, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        cls.name = tool_name

    def __init__(self, response_data: dict) -> None:
        self._response_data = response_data

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult.ok(data=self._response_data)


class FakeFreshserviceTool(FakeTool, tool_name="freshservice"):
    """Fake Freshservice tool."""


class FakeClickUpTool(FakeTool, tool_name="clickup"):
    """Fake ClickUp tool."""


class FakeLLMProvider(LLMProvider):
    """Fake LLM provider returning deterministic structured output."""

    def __init__(self, response: dict) -> None:
        self._response = response

    async def complete(self, prompt: str, context: dict | None = None) -> str:
        return self._response.get("summary", "")

    async def complete_structured(
        self,
        prompt: str,
        context: dict | None = None,
        schema: type | None = None,
    ) -> dict:
        return self._response


@pytest.fixture
def planner_agent() -> PlannerAgent:
    """Build a planner agent with a deterministic LLM."""
    return PlannerAgent(
        memory_facade=FakeMemoryFacade(),
        llm_provider=FakeLLMProvider(
            {
                "summary": "You have 2 tickets and 1 task today.",
                "plan": ["Review tickets", "Check task", "Update timesheet"],
            }
        ),
    )


@pytest.fixture
def agent_context() -> AgentContext:
    """Build an agent context with fake freshservice and clickup tools."""
    return AgentContext(
        tools=[
            FakeFreshserviceTool({"tickets": [{"id": "1"}, {"id": "2"}]}),
            FakeClickUpTool({"tasks": [{"id": "10"}]}),
        ]
    )


@pytest.mark.asyncio
async def test_planner_generates_morning_summary_with_llm(
    planner_agent: PlannerAgent,
    agent_context: AgentContext,
) -> None:
    """The planner agent uses the LLM to generate a morning summary event."""
    result = await planner_agent.handle(
        MorningSummaryRequested(),
        agent_context,
    )

    assert len(result.events) == 2
    generated = result.events[0]
    assert isinstance(generated, MorningSummaryGenerated)
    assert generated.summary == "You have 2 tickets and 1 task today."
    assert generated.plan == ["Review tickets", "Check task", "Update timesheet"]
