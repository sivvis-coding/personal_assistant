"""Tests for OpenAI LLM provider."""

import json
from types import SimpleNamespace

import pytest

from app.infrastructure.llm.openai_provider import OpenAILLMProvider


class _FakeMessage:
    def __init__(self, content=None, tool_calls=None) -> None:
        self.content = content
        self.tool_calls = tool_calls


class _FakeResponse:
    def __init__(self, message: _FakeMessage) -> None:
        self.choices = [SimpleNamespace(message=message)]


class _FakeCompletions:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def create(self, **kwargs):  # noqa: ANN003
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions(responses))


def _tool_call(call_id: str, name: str, arguments: str):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


class TestExtractJson:
    """Tests for _extract_json method."""

    @pytest.fixture
    def provider(self) -> OpenAILLMProvider:
        """Create provider with no API key (uses mock mode)."""
        from app.core.config import Settings

        settings = Settings(openai_api_key=None)
        return OpenAILLMProvider(settings)

    def should_parse_direct_json(self, provider: OpenAILLMProvider) -> None:
        """Clean JSON without markdown passes through directly."""
        content = '{"answer": "Hello", "tool_calls": []}'
        result = provider._extract_json(content)
        assert result == {"answer": "Hello", "tool_calls": []}

    def should_parse_json_with_markdown_code_block(self, provider: OpenAILLMProvider) -> None:
        """JSON wrapped in ```json ... ``` is extracted correctly."""
        content = '```json\n{"answer": "Hello", "tool_calls": []}\n```'
        result = provider._extract_json(content)
        assert result == {"answer": "Hello", "tool_calls": []}

    def should_parse_json_with_plain_markdown_block(self, provider: OpenAILLMProvider) -> None:
        """JSON wrapped in ``` ... ``` (no language tag) is extracted correctly."""
        content = '```\n{"answer": "Hello", "tool_calls": []}\n```'
        result = provider._extract_json(content)
        assert result == {"answer": "Hello", "tool_calls": []}

    def should_extract_first_json_when_extra_data_after(self, provider: OpenAILLMProvider) -> None:
        """When JSON is followed by extra text, only first object is parsed."""
        content = '{"answer": "Hello"}\n\nHere is some explanation text.'
        result = provider._extract_json(content)
        assert result == {"answer": "Hello"}

    def should_extract_first_json_when_multiple_concatenated(self, provider: OpenAILLMProvider) -> None:
        """When multiple JSON objects are concatenated, only first is parsed."""
        content = '{"first": true}\n{"second": true}'
        result = provider._extract_json(content)
        assert result == {"first": True}

    def should_handle_whitespace_before_json(self, provider: OpenAILLMProvider) -> None:
        """Leading/trailing whitespace is stripped."""
        content = '  \n\n{"answer": "Hello"}\n\n  '
        result = provider._extract_json(content)
        assert result == {"answer": "Hello"}

    def should_raise_on_genuinely_invalid_json(self, provider: OpenAILLMProvider) -> None:
        """When content is not JSON at all, JSONDecodeError is raised."""
        content = "This is not JSON at all"
        with pytest.raises(json.JSONDecodeError):
            provider._extract_json(content)

    def should_raise_on_malformed_json_object(self, provider: OpenAILLMProvider) -> None:
        """When content looks like JSON but is malformed, JSONDecodeError is raised."""
        content = '{"answer": "Hello", missing_quote: "value"}'
        with pytest.raises(json.JSONDecodeError):
            provider._extract_json(content)


class TestRunToolLoop:
    """Tests for the native function-calling loop."""

    @pytest.fixture
    def provider(self) -> OpenAILLMProvider:
        from app.core.config import Settings

        return OpenAILLMProvider(Settings(openai_api_key=None))

    @pytest.mark.asyncio
    async def should_execute_native_tool_then_return_final_json(
        self, provider: OpenAILLMProvider
    ) -> None:
        """A requested tool is dispatched, its result fed back, then JSON is returned."""
        responses = [
            _FakeResponse(_FakeMessage(tool_calls=[_tool_call("c1", "freshservice", '{"operation": "list"}')])),
            _FakeResponse(_FakeMessage(content='{"answer": "listo"}')),
        ]
        provider._client = _FakeClient(responses)
        provider._model = "gpt-test"

        executed: list[tuple[str, dict]] = []

        async def execute_tool(name: str, args: dict) -> dict:
            executed.append((name, args))
            return {"tool": name, "success": True, "data": {"count": 2}}

        schemas = [{"type": "function", "function": {"name": "freshservice", "parameters": {}}}]
        result = await provider.run_tool_loop(
            prompt="p", schema=None, tool_schemas=schemas, execute_tool=execute_tool
        )

        assert executed == [("freshservice", {"operation": "list"})]
        assert result == {"answer": "listo"}
        calls = provider._client.chat.completions.calls
        assert "tools" in calls[0]
        assert calls[1]["response_format"] == {"type": "json_object"}
        assert any(m.get("role") == "tool" for m in calls[1]["messages"])

    @pytest.mark.asyncio
    async def should_skip_tool_round_when_no_tools_provided(
        self, provider: OpenAILLMProvider
    ) -> None:
        """With no tool schemas, it goes straight to the structured completion."""
        provider._client = _FakeClient([_FakeResponse(_FakeMessage(content='{"answer": "hola"}'))])
        provider._model = "gpt-test"

        result = await provider.run_tool_loop(prompt="p", schema=None)

        assert result == {"answer": "hola"}
        assert len(provider._client.chat.completions.calls) == 1
