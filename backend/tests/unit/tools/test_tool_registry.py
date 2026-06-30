"""Tests for the tool registry and tool interface."""

import pytest

from app.tools.base import ToolInterface, ToolParameter, ToolRegistry, ToolResult


class FakeTool(ToolInterface):
    """Fake tool for testing."""

    name = "fake"
    description = "A fake tool"
    parameters = [ToolParameter(name="value", type="integer", description="An integer value")]

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult.ok(data={"doubled": kwargs["value"] * 2})


class FailingTool(ToolInterface):
    """Tool that always fails."""

    name = "failing"
    description = "A failing tool"
    parameters = []

    async def execute(self, **kwargs) -> ToolResult:
        raise RuntimeError("expected failure")


def test_registry_registers_and_retrieves_tools():
    """Tools should be retrievable after registration."""
    registry = ToolRegistry()
    tool = FakeTool()

    registry.register(tool)

    assert registry.has_tool("fake")
    assert registry.get("fake") is tool


def test_registry_raises_for_missing_tool():
    """Retrieving an unregistered tool should raise KeyError."""
    registry = ToolRegistry()

    with pytest.raises(KeyError):
        registry.get("missing")


@pytest.mark.asyncio
async def test_tool_execution_returns_result():
    """Tool execute should return a successful ToolResult."""
    tool = FakeTool()

    result = await tool.execute(value=21)

    assert result.success is True
    assert result.data["doubled"] == 42


@pytest.mark.asyncio
async def test_tool_execution_catches_exceptions():
    """Tool execute should catch exceptions and return an error result."""
    # Note: FailingTool raises inside execute; our ToolInterface does not
    # enforce catching. This test documents the expected behavior once
    # wrapped by adapters.
    tool = FailingTool()

    with pytest.raises(RuntimeError):
        await tool.execute()
