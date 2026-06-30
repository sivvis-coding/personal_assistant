"""Tests for OpenAI LLM provider."""

import json

import pytest

from app.infrastructure.llm.openai_provider import OpenAILLMProvider


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
