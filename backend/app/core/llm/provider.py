"""LLM provider abstraction for agent use.

The provider hides the underlying LLM client (OpenAI, local models, etc.) behind
a simple async interface that agents can call without knowing implementation details.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class LLMProvider(ABC):
    """Abstract LLM provider for agent consumption.

    Implementations must support both free-text and structured (JSON) completions.
    When no API key is configured, implementations should return deterministic mock
    output so agents can be tested and developed without external calls.

    Parameters:
        None.

    Returns:
        LLM provider instance.
    """

    @abstractmethod
    async def complete(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Return a free-text completion for the given prompt.

        Parameters:
            prompt: Prompt text to send to the model.
            context: Optional structured context appended to the prompt.

        Returns:
            Model response text.

        Edge cases:
            Missing credentials should return mock output, never raise.
        """

    @abstractmethod
    async def complete_structured(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        schema: type[Any] | None = None,
    ) -> dict[str, Any]:
        """Return a structured (JSON) completion for the given prompt.

        Parameters:
            prompt: Prompt text to send to the model.
            context: Optional structured context appended to the prompt.
            schema: Optional schema used to validate or guide the response.

        Returns:
            Parsed JSON object.

        Edge cases:
            Missing credentials should return mock output compatible with the schema.
        """

    async def run_tool_loop(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        schema: type[Any] | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
        execute_tool: ToolExecutor | None = None,
        max_iterations: int = 4,
    ) -> dict[str, Any]:
        """Run a native tool-calling loop, then return the final structured response.

        The model may call any of ``tool_schemas`` (executed via ``execute_tool``)
        for up to ``max_iterations`` rounds before producing the final answer,
        which is validated against ``schema``.

        Default implementation has no native tool-calling: it ignores the tools
        and performs a single structured completion. Providers that support
        function-calling override this.
        """
        return await self.complete_structured(prompt, context, schema)

    async def stream_tool_loop(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        schema: type[Any] | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
        execute_tool: ToolExecutor | None = None,
        max_iterations: int = 4,
    ) -> AsyncIterator[dict[str, Any]]:
        """Like run_tool_loop, but streams the final answer as token events.

        Default implementation resolves tools non-streaming, then emits the
        answer as a single token event followed by 'done'.
        """
        data = await self.run_tool_loop(
            prompt, context, schema, tool_schemas, execute_tool, max_iterations
        )
        answer = data.get("answer", "") if isinstance(data, dict) else ""
        if answer:
            yield {"type": "token", "text": answer}
        yield {"type": "done", "data": data}
