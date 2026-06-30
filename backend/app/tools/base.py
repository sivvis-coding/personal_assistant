"""Tool abstraction and registry."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    """Result returned by a tool execution.

    Parameters:
        success: Whether the tool executed successfully.
        data: Structured result data.
        message: Human-readable message.

    Returns:
        Tool result instance.
    """

    success: bool
    data: Any = None
    message: str = ""

    @classmethod
    def ok(cls, data: Any = None, message: str = "") -> "ToolResult":
        """Create a successful tool result."""
        return cls(success=True, data=data, message=message)

    @classmethod
    def error(cls, message: str, data: Any = None) -> "ToolResult":
        """Create a failed tool result."""
        return cls(success=False, data=data, message=message)


@dataclass(frozen=True)
class ToolParameter:
    """Description of a tool parameter."""

    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


class ToolInterface(ABC):
    """Base class for all tools.

    A tool wraps an external integration or internal capability behind a
    uniform interface so agents can call them without knowing implementation
    details.

    Parameters:
        name: Unique tool name.
        description: Human-readable description.
        parameters: List of accepted parameters.

    Returns:
        Tool instance.
    """

    name: str
    description: str
    parameters: list[ToolParameter]

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with the given parameters.

        Parameters:
            **kwargs: Tool-specific parameters.

        Returns:
            Tool execution result.
        """


class ToolRegistry:
    """Global registry for tools.

    Tools are registered by name and retrieved by agents at runtime. The
    registry is intentionally simple; it does not validate parameter schemas.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._tools: dict[str, ToolInterface] = {}

    def register(self, tool: ToolInterface) -> None:
        """Register a tool.

        Parameters:
            tool: Tool instance to register.

        Returns:
            None.

        Edge cases:
            Registering a tool with a duplicate name overwrites the previous
            registration.
        """
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolInterface:
        """Get a tool by name.

        Parameters:
            name: Tool name.

        Returns:
            Tool instance.

        Edge cases:
            Raises KeyError if the tool is not registered.
        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered")
        return self._tools[name]

    def list_tools(self) -> list[ToolInterface]:
        """Return all registered tools."""
        return list(self._tools.values())

    def has_tool(self, name: str) -> bool:
        """Return whether a tool is registered."""
        return name in self._tools
