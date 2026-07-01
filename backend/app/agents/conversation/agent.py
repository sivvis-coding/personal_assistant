"""Conversation agent for general assistant chat."""

from pathlib import Path
from typing import Any

from app.agents.conversation.schemas import ConversationResponse, ToolCall
from app.agents.time.agent import TimeAgent
from app.core.llm.provider import LLMProvider
from app.assistant.schemas.context import AssistantContext
from app.tools.base import ToolInterface, ToolResult


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


def _tool_descriptions(tools: list[ToolInterface]) -> list[dict[str, Any]]:
    """Return a JSON-serializable description of available tools."""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": [
                {"name": param.name, "type": param.type, "description": param.description, "required": param.required}
                for param in tool.parameters
            ],
        }
        for tool in tools
    ]


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
        prompt = _load_prompt("conversation_v1.txt")
        base_context = {
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
            "available_tools": _tool_descriptions(tools),
            "agent_instructions": context.agent_system_prompt,
        }

        tool_results: list[dict[str, Any]] = []
        last_response: ConversationResponse | None = None

        for _ in range(self._max_tool_iterations):
            llm_context = {**base_context, "tool_results": tool_results}
            response_data = await self._llm_provider.complete_structured(
                prompt=prompt,
                context=llm_context,
                schema=ConversationResponse,
            )
            response = ConversationResponse.model_validate(response_data)
            last_response = response

            if not response.tool_calls:
                return response

            tool_results = await self._execute_tool_calls(response.tool_calls, tools)

        return last_response or ConversationResponse(answer="No pude completar la consulta.")

    async def _execute_tool_calls(
        self,
        tool_calls: list[ToolCall],
        tools: list[ToolInterface],
    ) -> list[dict[str, Any]]:
        """Execute requested tool calls and return their results.

        Parameters:
            tool_calls: Tool calls requested by the LLM.
            tools: Available tools.

        Returns:
            List of tool results with tool name and result data or error.

        Edge cases:
            Unknown tools return an error result instead of raising.
        """
        results: list[dict[str, Any]] = []
        tool_map = {tool.name: tool for tool in tools}

        for call in tool_calls:
            tool = tool_map.get(call.tool)
            if tool is None:
                results.append(
                    {
                        "tool": call.tool,
                        "error": f"Tool '{call.tool}' is not available",
                    }
                )
                continue

            try:
                result: ToolResult = await tool.execute(
                    operation=call.operation,
                    **call.parameters,
                )
                results.append(
                    {
                        "tool": call.tool,
                        "operation": call.operation,
                        "success": result.success,
                        "data": result.data,
                        "message": result.message,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "tool": call.tool,
                        "operation": call.operation,
                        "success": False,
                        "error": str(exc),
                    }
                )

        return results

    @staticmethod
    def is_time_tracking_request(message: str) -> bool:
        """Delegate time-tracking detection to TimeAgent.

        Parameters:
            message: User message text.

        Returns:
            True when the message looks like a time-tracking request.
        """
        return TimeAgent.is_time_tracking_request(message)
