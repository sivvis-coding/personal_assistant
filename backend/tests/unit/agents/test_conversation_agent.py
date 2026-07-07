"""Tests for the conversation agent."""

import pytest

from app.agents.conversation.agent import ConversationAgent
from app.agents.conversation.schemas import ConversationResponse
from app.core.llm.provider import LLMProvider
from app.assistant.schemas.actions import AssistantActionCreate
from app.assistant.schemas.context import AssistantContext
from app.assistant.schemas.recommendations import PrioritizedWorkPlan
from app.schemas.clickup import WeekTimeResponse
from app.schemas.ticket import Ticket, TicketRequester
from app.tools.base import ToolInterface, ToolResult


class FakeLLMProvider(LLMProvider):
    """Fake LLM provider returning deterministic structured output."""

    def __init__(self, response: dict) -> None:
        self._response = response
        self.last_context: dict | None = None

    async def complete(self, prompt: str, context: dict | None = None) -> str:
        self.last_context = context
        return self._response.get("answer", "")

    async def complete_structured(
        self,
        prompt: str,
        context: dict | None = None,
        schema: type | None = None,
    ) -> dict:
        self.last_context = context
        return self._response


def make_context() -> AssistantContext:
    """Build a minimal assistant context."""
    return AssistantContext(
        tickets=[
            Ticket(
                id="1001",
                subject="Test ticket",
                status="open",
                priority="medium",
                requester=TicketRequester(name="Ada Lovelace", email="ada@example.com"),
                description="Test description.",
                raw={},
            )
        ],
        ticket_source="mock",
        week_time=WeekTimeResponse(source="mock", week_start="2026-06-22", week_end="2026-06-28", total_hours=0, entries=[]),
        existing_backlog_ticket_ids=[],
    )


@pytest.mark.asyncio
async def test_respond_returns_structured_response() -> None:
    """The conversation agent parses the LLM response into a ConversationResponse."""
    agent = ConversationAgent(
        llm_provider=FakeLLMProvider(
            {
                "answer": "Tienes 1 ticket abierto.",
                "needs_clarification": False,
                "clarification_question": "",
                "proposed_actions": [],
            }
        )
    )

    result = await agent.respond("Hola, ¿qué tengo pendiente?", make_context(), tools=[])

    assert isinstance(result, ConversationResponse)
    assert result.answer == "Tienes 1 ticket abierto."
    assert not result.needs_clarification
    assert result.proposed_actions == []


@pytest.mark.asyncio
async def test_respond_parses_proposed_actions() -> None:
    """The conversation agent converts LLM actions into AssistantActionCreate objects."""
    agent = ConversationAgent(
        llm_provider=FakeLLMProvider(
            {
                "answer": "Voy a preparar la tarea en ClickUp.",
                "needs_clarification": False,
                "clarification_question": "",
                "proposed_actions": [
                    {
                        "action_type": "send_ticket_to_backlog",
                        "title": "Pasar ticket 1001 al backlog",
                        "description": "Crear tarea en ClickUp a partir del ticket",
                        "ticket_id": "1001",
                        "payload": {"body": "Lo pasamos a backlog"},
                    }
                ],
            }
        )
    )

    result = await agent.respond("Pasa el ticket 1001 al backlog", make_context(), tools=[])

    assert len(result.proposed_actions) == 1
    action = result.proposed_actions[0]
    assert isinstance(action, AssistantActionCreate)
    assert action.action_type == "send_ticket_to_backlog"
    assert action.ticket_id == "1001"


class FakeTool(ToolInterface):
    """Fake tool returning deterministic results."""

    name = "freshservice"
    description = "Fake freshservice tool"
    parameters = []

    def __init__(self, response_data: dict) -> None:
        self._response_data = response_data

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult.ok(data=self._response_data)


class ToolInvokingProvider(LLMProvider):
    """Fake provider that drives the agent's native tool executor.

    It records the tool schemas it was handed and dispatches each requested
    (name, args) pair through the agent-supplied ``execute_tool`` callback so
    tests can assert on how the agent wires tools without a real OpenAI client.
    """

    def __init__(self, calls: list[tuple[str, dict]]) -> None:
        self._calls = calls
        self.tool_results: list[dict] = []
        self.tool_schemas: list[dict] | None = None
        self.last_context: dict | None = None

    async def complete(self, prompt: str, context: dict | None = None) -> str:
        return ""

    async def complete_structured(
        self,
        prompt: str,
        context: dict | None = None,
        schema: type | None = None,
    ) -> dict:
        return {"answer": ""}

    async def run_tool_loop(
        self,
        prompt: str,
        context: dict | None = None,
        schema: type | None = None,
        tool_schemas: list[dict] | None = None,
        execute_tool=None,
        max_iterations: int = 4,
    ) -> dict:
        self.last_context = context
        self.tool_schemas = tool_schemas
        for name, args in self._calls:
            self.tool_results.append(await execute_tool(name, args))
        return {
            "answer": f"Resolví {len(self.tool_results)} llamada(s).",
            "needs_clarification": False,
            "clarification_question": "",
            "proposed_actions": [],
        }


def test_is_time_tracking_request_delegates_to_time_agent() -> None:
    """The conversation agent delegates time-tracking detection to TimeAgent."""
    assert ConversationAgent.is_time_tracking_request("imputa 2h hoy")
    assert not ConversationAgent.is_time_tracking_request("hola")


@pytest.mark.asyncio
async def test_respond_dispatches_native_tool_calls() -> None:
    """The agent exposes tools as schemas and dispatches native calls to them."""
    provider = ToolInvokingProvider([("freshservice", {"operation": "list", "scope": "mine"})])
    agent = ConversationAgent(llm_provider=provider)
    tool = FakeTool({"tickets": [{"id": "1"}, {"id": "2"}]})

    result = await agent.respond("¿Cuántos tickets tengo?", make_context(), tools=[tool])

    # Tool was exposed as a native function schema.
    assert provider.tool_schemas is not None
    assert provider.tool_schemas[0]["function"]["name"] == "freshservice"
    # The agent's executor ran the tool and returned its data.
    assert provider.tool_results[0]["success"] is True
    assert provider.tool_results[0]["data"] == {"tickets": [{"id": "1"}, {"id": "2"}]}
    assert result.answer == "Resolví 1 llamada(s)."


@pytest.mark.asyncio
async def test_respond_reports_unknown_tools_without_crashing() -> None:
    """The agent's executor returns an error payload for unknown tool names."""
    provider = ToolInvokingProvider([("unknown_tool", {"operation": "list"})])
    agent = ConversationAgent(llm_provider=provider)

    result = await agent.respond("Consulta datos", make_context(), tools=[])

    assert "error" in provider.tool_results[0]
    assert "not available" in provider.tool_results[0]["error"]
    assert result.answer == "Resolví 1 llamada(s)."


class ReadOnlyTool(ToolInterface):
    """Tool that only permits read operations."""

    name = "freshservice"
    description = "Read Freshservice tickets."
    read_operations = ["list", "get"]
    parameters = []

    def __init__(self) -> None:
        self.executed = False

    async def execute(self, **kwargs) -> ToolResult:
        self.executed = True
        return ToolResult.ok(data={"ok": True})


@pytest.mark.asyncio
async def test_executor_blocks_write_operations() -> None:
    """A non-read operation is rejected without invoking the tool (HITL guard)."""
    provider = ToolInvokingProvider([("freshservice", {"operation": "reply", "body": "x"})])
    agent = ConversationAgent(llm_provider=provider)
    tool = ReadOnlyTool()

    await agent.respond("Responde el ticket", make_context(), tools=[tool])

    assert tool.executed is False
    assert "not permitted" in provider.tool_results[0]["error"]


@pytest.mark.asyncio
async def test_respond_includes_message_history_in_context() -> None:
    """The conversation agent passes conversation history to the LLM provider."""
    fake_llm = FakeLLMProvider(
        {
            "answer": "OK",
            "needs_clarification": False,
            "clarification_question": "",
            "proposed_actions": [],
        }
    )
    agent = ConversationAgent(llm_provider=fake_llm)
    history = [
        {"user_message": "Hola", "assistant_answer": "Hola, ¿en qué puedo ayudarte?"},
    ]

    await agent.respond("¿Qué tengo pendiente?", make_context(), tools=[], message_history=history)

    assert fake_llm.last_context is not None
    assert fake_llm.last_context["message_history"] == history
    assert fake_llm.last_context["current_message"] == "¿Qué tengo pendiente?"
