"""Conversation agent for general assistant chat."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from app.agents.conversation.schemas import ConversationResponse
from app.agents.conversation.tool_schemas import build_tool_schemas
from app.agents.time.agent import TimeAgent
from app.core.llm.provider import LLMProvider, ToolExecutor
from app.assistant.schemas.context import AssistantContext
from app.tools.base import ToolInterface


def _load_prompt(prompt_file: str) -> str:
    """Load a versioned prompt file from the conversation prompts directory.

    Parameters:
        prompt_file: Prompt file name.

    Returns:
        Prompt text.

    Edge cases:
        Missing prompt file raises FileNotFoundError because deployment is invalid.
    """
    return (Path(__file__).resolve().parent / "prompts" / prompt_file).read_text(encoding="utf-8")


def _jsonable(value: Any) -> Any:
    """Make a tool result payload JSON-serializable for the model."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


class ConversationAgent:
    """Agent that handles general assistant conversation turns with an LLM.

    This agent does NOT inherit from BaseAgent because it is designed for
    synchronous chat responses. It may be migrated to event-driven later.

    Parameters:
        llm_provider: LLM provider for generating responses.
        max_tool_iterations: Maximum number of tool call rounds per turn.

    Returns:
        Conversation agent instance.
    """

    def __init__(self, llm_provider: LLMProvider, max_tool_iterations: int = 3) -> None:
        self._llm_provider = llm_provider
        self._max_tool_iterations = max_tool_iterations

    async def respond(
        self,
        message: str,
        context: AssistantContext,
        tools: list[ToolInterface],
        message_history: list[dict[str, Any]] | None = None,
    ) -> ConversationResponse:
        """Generate a response for a general (non-time-tracking) user message.

        Parameters:
            message: User message text.
            context: Current assistant context with tickets and time data.
            tools: Tools the agent may call to fetch live data.
            message_history: Optional recent conversation turns.

        Returns:
            Structured conversation response with answer and proposed actions.

        Edge cases:
            Time tracking requests should be routed to TimeAgent by the caller.
            Unknown tools requested by the LLM are skipped and reported.
            LLM failures are surfaced as-is so the service can decide how to handle them.
        """
        response_data = await self._llm_provider.run_tool_loop(
            prompt=_load_prompt("conversation_v1.txt"),
            context=self._build_context(message, context, message_history),
            schema=ConversationResponse,
            tool_schemas=build_tool_schemas(tools),
            execute_tool=self._make_executor(tools),
            max_iterations=self._max_tool_iterations,
        )
        return ConversationResponse.model_validate(response_data)

    def _build_context(
        self,
        message: str,
        context: AssistantContext,
        message_history: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Assemble the LLM context payload for a conversation turn."""
        return {
            "message_history": message_history or [],
            "current_message": message,
            "context": {
                "tickets": [ticket.model_dump() for ticket in context.tickets],
                "ticket_source": context.ticket_source,
                "week_time": context.week_time.model_dump(),
                "existing_backlog_ticket_ids": context.existing_backlog_ticket_ids,
                "clickup_lists": [lst.model_dump() for lst in context.clickup_lists],
                "user_preferences": context.user_preferences,
            },
            "agent_instructions": context.agent_system_prompt,
        }

    def _make_executor(self, tools: list[ToolInterface]) -> ToolExecutor:
        """Return a callback that dispatches native tool calls to registered tools.

        Only read operations are allowed: writes must be proposed as HITL actions,
        never executed inline. This enforces the read-only contract even if the
        model requests an operation outside the schema's advertised enum.

        Edge cases:
            Unknown tool names, disallowed operations and tool exceptions are
            returned as error payloads rather than raised, so a single bad call
            does not abort the turn.
        """
        tool_map = {tool.name: tool for tool in tools}

        async def _execute(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            tool = tool_map.get(name)
            if tool is None:
                return {"tool": name, "error": f"Tool '{name}' is not available"}
            allowed = getattr(tool, "read_operations", []) or []
            operation = arguments.get("operation")
            if allowed and operation not in allowed:
                return {
                    "tool": name,
                    "error": f"Operation '{operation}' is not permitted here; propose it as an action instead.",
                }
            try:
                result = await tool.execute(**arguments)
                return {
                    "tool": name,
                    "success": result.success,
                    "data": _jsonable(result.data),
                    "message": result.message,
                }
            except Exception as exc:  # noqa: BLE001
                return {"tool": name, "success": False, "error": str(exc)}

        return _execute

    async def respond_stream(
        self,
        message: str,
        context: AssistantContext,
        tools: list[ToolInterface],
        message_history: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Like respond(), but streams the final answer as SSE token events.

        Resolves any native tool calls non-streaming, then streams the final
        answer for real-time UX.

        Yields dicts:
            {"type": "token", "text": str} — incremental answer text
            {"type": "done", "data": dict} — full ConversationResponse dump
            {"type": "error", "message": str} — on failure
        """
        async for event in self._llm_provider.stream_tool_loop(
            prompt=_load_prompt("conversation_v1.txt"),
            context=self._build_context(message, context, message_history),
            schema=ConversationResponse,
            tool_schemas=build_tool_schemas(tools),
            execute_tool=self._make_executor(tools),
            max_iterations=self._max_tool_iterations,
        ):
            yield event

    @staticmethod
    def is_time_tracking_request(message: str) -> bool:
        """Delegate time-tracking detection to TimeAgent.

        Parameters:
            message: User message text.

        Returns:
            True when the message looks like a time-tracking request.
        """
        return TimeAgent.is_time_tracking_request(message)
