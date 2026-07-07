"""OpenAI-backed LLM provider implementation."""

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ExternalServiceError
from app.core.llm.provider import LLMProvider, ToolExecutor


class _AnswerExtractor:
    """Extract the value of the JSON 'answer' key from a streaming token sequence."""

    _PATTERNS = ('"answer": "', '"answer":"', '"answer" : "', '"answer" :"')

    def __init__(self) -> None:
        self._buf = ""
        self._in_value = False
        self._done = False
        self._escape = False

    def feed(self, chunk: str) -> str:
        """Feed a chunk of raw JSON tokens; return extracted answer characters."""
        out: list[str] = []
        for ch in chunk:
            if self._done:
                break
            if not self._in_value:
                self._buf += ch
                if len(self._buf) > 40:
                    self._buf = self._buf[-20:]
                if any(self._buf.endswith(p) for p in self._PATTERNS):
                    self._in_value = True
            else:
                if self._escape:
                    self._escape = False
                    if ch == "n":
                        out.append("\n")
                    elif ch == "t":
                        out.append("\t")
                    elif ch == "r":
                        out.append("\r")
                    elif ch in ('"', "\\", "/"):
                        out.append(ch)
                    else:
                        out.append(ch)
                elif ch == "\\":
                    self._escape = True
                elif ch == '"':
                    self._done = True
                else:
                    out.append(ch)
        return "".join(out)


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

    async def run_tool_loop(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        schema: type[Any] | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
        execute_tool: ToolExecutor | None = None,
        max_iterations: int = 4,
    ) -> dict[str, Any]:
        """Resolve any native tool calls, then return the final structured response."""
        if self._client is None:
            return self._mock_structured_response(prompt, context, schema)

        messages = self._build_messages(prompt, context)
        try:
            await self._resolve_tool_calls(messages, tool_schemas, execute_tool, max_iterations)
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
            raise ExternalServiceError(f"OpenAI tool loop failed: {error}") from error

    async def stream_tool_loop(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        schema: type[Any] | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
        execute_tool: ToolExecutor | None = None,
        max_iterations: int = 4,
    ) -> AsyncIterator[dict[str, Any]]:
        """Resolve native tool calls non-streaming, then stream the final answer."""
        if self._client is None:
            mock = self._mock_structured_response(prompt, context, schema)
            answer = mock.get("answer", "") if isinstance(mock, dict) else ""
            if answer:
                yield {"type": "token", "text": answer}
            yield {"type": "done", "data": mock}
            return

        messages = self._build_messages(prompt, context)
        try:
            await self._resolve_tool_calls(messages, tool_schemas, execute_tool, max_iterations)
        except OpenAIError as error:
            yield {"type": "error", "message": f"OpenAI tool loop failed: {error}"}
            return

        extractor = _AnswerExtractor()
        full_content = ""
        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=messages,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if not delta:
                    continue
                full_content += delta
                tokens = extractor.feed(delta)
                if tokens:
                    yield {"type": "token", "text": tokens}
        except OpenAIError as error:
            yield {"type": "error", "message": f"OpenAI streaming failed: {error}"}
            return

        try:
            data = self._extract_json(full_content)
            if schema is not None:
                data = schema.model_validate(data).model_dump()
            yield {"type": "done", "data": data}
        except (json.JSONDecodeError, ValidationError) as error:
            yield {"type": "error", "message": f"Response parsing failed: {error}"}

    async def _resolve_tool_calls(
        self,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]] | None,
        execute_tool: ToolExecutor | None,
        max_iterations: int,
    ) -> None:
        """Run native function-calling rounds, appending tool results to messages.

        Loops until the model stops requesting tools or max_iterations is reached.
        Each requested call is dispatched through execute_tool and its result is
        appended as a 'tool' message so the model can use it on the next round.
        """
        if not tool_schemas or execute_tool is None:
            return

        for _ in range(max_iterations):
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=tool_schemas,
                tool_choice="auto",
            )
            message = response.choices[0].message
            if not message.tool_calls:
                return

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.function.name, "arguments": call.function.arguments},
                        }
                        for call in message.tool_calls
                    ],
                }
            )
            results = await asyncio.gather(
                *(self._invoke_tool(execute_tool, call) for call in message.tool_calls)
            )
            messages.extend(results)

    @staticmethod
    async def _invoke_tool(execute_tool: ToolExecutor, tool_call: Any) -> dict[str, Any]:
        """Execute a single tool call and wrap the result as a 'tool' message."""
        try:
            arguments = json.loads(tool_call.function.arguments or "{}")
        except json.JSONDecodeError:
            arguments = {}
        result = await execute_tool(tool_call.function.name, arguments)
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result, default=str, ensure_ascii=False),
        }

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
        messages: list[dict[str, str]] = [{"role": "system", "content": prompt}]

        ctx = dict(context or {})
        history: list[dict[str, Any]] = ctx.pop("message_history", [])

        for turn in history:
            user_msg = turn.get("user_message", "")
            assistant_msg = turn.get("assistant_answer", "")
            if user_msg:
                messages.append({"role": "user", "content": user_msg})
            if assistant_msg:
                messages.append({"role": "assistant", "content": assistant_msg})

        if ctx:
            messages.append(
                {"role": "user", "content": f"Context: {json.dumps(ctx, default=str, ensure_ascii=False)}"}
            )
        elif not history:
            messages.append({"role": "user", "content": "Proceed."})

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
