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
                        "action_type": "prepare_clickup_task",
                        "title": "Preparar tarea para ticket 1001",
                        "description": "Crear user story a partir del ticket",
                        "ticket_id": "1001",
                        "payload": {"subject": "Test ticket"},
                    }
                ],
            }
        )
    )

    result = await agent.respond("Pasa el ticket 1001 al backlog", make_context(), tools=[])

    assert len(result.proposed_actions) == 1
    action = result.proposed_actions[0]
    assert isinstance(action, AssistantActionCreate)
    assert action.action_type == "prepare_clickup_task"
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


class MultiTurnFakeLLMProvider(LLMProvider):
    """Fake LLM provider that returns different responses on each call."""

    def __init__(self, responses: list[dict]) -> None:
        self._responses = responses
        self._call_index = 0
        self.last_context: dict | None = None

    async def complete(self, prompt: str, context: dict | None = None) -> str:
        self.last_context = context
        response = self._responses[self._call_index]
        self._call_index = min(self._call_index + 1, len(self._responses) - 1)
        return response.get("answer", "")

    async def complete_structured(
        self,
        prompt: str,
        context: dict | None = None,
        schema: type | None = None,
    ) -> dict:
        self.last_context = context
        response = self._responses[self._call_index]
        self._call_index = min(self._call_index + 1, len(self._responses) - 1)
        return response


def test_is_time_tracking_request_delegates_to_time_agent() -> None:
    """The conversation agent delegates time-tracking detection to TimeAgent."""
    assert ConversationAgent.is_time_tracking_request("imputa 2h hoy")
    assert not ConversationAgent.is_time_tracking_request("hola")


@pytest.mark.asyncio
async def test_respond_executes_tool_calls_and_returns_final_answer() -> None:
    """The agent calls tools when requested and returns the final LLM answer."""
    agent = ConversationAgent(
        llm_provider=MultiTurnFakeLLMProvider(
            [
                {
                    "answer": "",
                    "tool_calls": [
                        {"tool": "freshservice", "operation": "list", "parameters": {"scope": "mine"}}
                    ],
                    "needs_clarification": False,
                    "clarification_question": "",
                    "proposed_actions": [],
                },
                {
                    "answer": "Tienes 2 tickets abiertos.",
                    "tool_calls": [],
                    "needs_clarification": False,
                    "clarification_question": "",
                    "proposed_actions": [],
                },
            ]
        )
    )
    tool = FakeTool({"tickets": [{"id": "1"}, {"id": "2"}]})

    result = await agent.respond("¿Cuántos tickets tengo?", make_context(), tools=[tool])

    assert result.answer == "Tienes 2 tickets abiertos."
    assert result.tool_calls == []


@pytest.mark.asyncio
async def test_respond_skips_unknown_tools() -> None:
    """The agent reports errors for unknown tools without crashing."""
    agent = ConversationAgent(
        llm_provider=MultiTurnFakeLLMProvider(
            [
                {
                    "answer": "",
                    "tool_calls": [
                        {"tool": "unknown_tool", "operation": "list", "parameters": {}}
                    ],
                    "needs_clarification": False,
                    "clarification_question": "",
                    "proposed_actions": [],
                },
                {
                    "answer": "No pude consultar la tool solicitada.",
                    "tool_calls": [],
                    "needs_clarification": False,
                    "clarification_question": "",
                    "proposed_actions": [],
                },
            ]
        )
    )

    result = await agent.respond("Consulta datos", make_context(), tools=[])

    assert "No pude consultar" in result.answer


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
