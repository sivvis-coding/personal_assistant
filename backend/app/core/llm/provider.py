"""LLM provider abstraction for agent use.

The provider hides the underlying LLM client (OpenAI, local models, etc.) behind
a simple async interface that agents can call without knowing implementation details.
"""

from abc import ABC, abstractmethod
from typing import Any


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
