"""OpenAI-backed LLM provider implementation."""

import json
import re
from typing import Any

from openai import AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ExternalServiceError
from app.core.llm.provider import LLMProvider


class OpenAILLMProvider(LLMProvider):
    """LLM provider that calls OpenAI chat completions.

    Parameters:
        settings: Application settings with OpenAI credentials and model.

    Returns:
        LLM provider instance.

    Edge cases:
        Missing API key returns deterministic mock output for local development.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.has_openai_key else None
        self._model = settings.openai_model

    async def complete(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Return a free-text completion from OpenAI.

        Parameters:
            prompt: Prompt text.
            context: Optional structured context.

        Returns:
            Model response text or mock output when not configured.
        """
        if self._client is None:
            return self._mock_text_response(prompt, context)

        messages = self._build_messages(prompt, context)
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
            return response.choices[0].message.content or ""
        except OpenAIError as error:
            raise ExternalServiceError(f"OpenAI completion failed: {error}") from error

    async def complete_structured(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        schema: type[Any] | None = None,
    ) -> dict[str, Any]:
        """Return a structured JSON completion from OpenAI.

        Parameters:
            prompt: Prompt text.
            context: Optional structured context.
            schema: Optional Pydantic schema for validation.

        Returns:
            Parsed JSON object or mock output when not configured.
        """
        if self._client is None:
            return self._mock_structured_response(prompt, context, schema)

        messages = self._build_messages(prompt, context)
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=messages,
            )
            content = response.choices[0].message.content or "{}"
            data = self._extract_json(content)
            if schema is not None:
                return schema.model_validate(data).model_dump()
            return data
        except (OpenAIError, json.JSONDecodeError, ValidationError) as error:
            raise ExternalServiceError(f"OpenAI structured completion failed: {error}") from error

    def _extract_json(self, content: str) -> dict[str, Any]:
        """Extract JSON object from potentially malformed content.

        Handles common LLM output issues:
        - Markdown code blocks (```json ... ```)
        - Text before/after valid JSON
        - Multiple concatenated JSON objects

        Parameters:
            content: Raw response content from LLM.

        Returns:
            Parsed JSON object.

        Raises:
            JSONDecodeError: When no valid JSON found in content.
        """
        # Step 1: Strip whitespace
        content = content.strip()

        # Step 2: Remove markdown code blocks
        # Matches ```json ... ``` or ``` ... ``` with optional language tag
        code_block_pattern = r"^```(?:json)?\s*\n?(.*?)\n?\s*```$"
        match = re.match(code_block_pattern, content, re.DOTALL)
        if match:
            content = match.group(1).strip()

        # Step 3: Try direct parse first (fast path for correct output)
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            # If error is NOT "Extra data", content is genuinely invalid JSON
            if "Extra data" not in str(exc):
                raise

        # Step 4: "Extra data" error - extract first valid JSON object
        # JSONDecoder.raw_decode() returns (object, end_index) and ignores trailing data
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(content)
        return obj

    def _build_messages(
        self,
        prompt: str,
        context: dict[str, Any] | None,
    ) -> list[dict[str, str]]:
        """Build OpenAI messages from prompt and optional context.

        If the context contains a 'message_history' list of user/assistant turns,
        each turn is injected as a real chat message so the model sees the full
        conversation rather than serialised JSON.
        """
        messages: list[dict[str, str]] = [
            {"role": "system", "content": "You are a helpful personal assistant."}
        ]

        ctx = dict(context or {})
        history: list[dict[str, Any]] = ctx.pop("message_history", [])

        for turn in history:
            user_msg = turn.get("user_message", "")
            assistant_msg = turn.get("assistant_answer", "")
            if user_msg:
                messages.append({"role": "user", "content": user_msg})
            if assistant_msg:
                messages.append({"role": "assistant", "content": assistant_msg})

        content = prompt
        if ctx:
            content += f"\n\nContext: {json.dumps(ctx, default=str, ensure_ascii=False)}"
        messages.append({"role": "user", "content": content})

        return messages

    def _mock_text_response(self, prompt: str, context: dict[str, Any] | None) -> str:
        """Return deterministic text output when OpenAI is not configured."""
        return (
            "Mock LLM response: OpenAI API key is not configured. "
            "Returning a safe placeholder based on the prompt."
        )

    def _mock_structured_response(
        self,
        prompt: str,
        context: dict[str, Any] | None,
        schema: type[Any] | None,
    ) -> dict[str, Any]:
        """Return deterministic structured output when OpenAI is not configured."""
        if schema is not None:
            try:
                instance = schema.model_construct()
                return instance.model_dump()
            except Exception:  # noqa: BLE001
                pass
        return {"mock": True, "note": "OpenAI API key is not configured"}
