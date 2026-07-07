"""Tests for building OpenAI function schemas from tools."""

from app.agents.conversation.tool_schemas import build_tool_schemas, to_openai_function
from app.tools.base import ToolInterface, ToolParameter, ToolResult


class _SampleTool(ToolInterface):
    name = "freshservice"
    description = "Read and update Freshservice tickets."
    parameters = [
        ToolParameter(name="operation", type="string", description="One of: list, get, search"),
        ToolParameter(name="ticket_id", type="string", description="Ticket id", required=False),
        ToolParameter(name="changes", type="object", description="Fields to update", required=False),
    ]

    async def execute(self, **kwargs) -> ToolResult:  # noqa: ANN003
        return ToolResult.ok()


def test_operation_description_becomes_enum() -> None:
    """The 'One of: ...' convention is turned into a JSON-Schema enum."""
    function = to_openai_function(_SampleTool())["function"]
    properties = function["parameters"]["properties"]

    assert properties["operation"]["enum"] == ["list", "get", "search"]
    assert function["name"] == "freshservice"


def test_required_params_and_object_type() -> None:
    """Only required params are listed; object params map to a JSON object type."""
    function = to_openai_function(_SampleTool())["function"]

    assert function["parameters"]["required"] == ["operation"]
    assert function["parameters"]["properties"]["changes"]["type"] == "object"
    assert function["parameters"]["properties"]["changes"]["additionalProperties"] is True


def test_build_tool_schemas_wraps_each_tool() -> None:
    """Each tool is wrapped as a native function tool schema."""
    schemas = build_tool_schemas([_SampleTool()])

    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"


class _ReadWriteTool(ToolInterface):
    name = "clickup"
    description = "Create, update and read ClickUp tasks."
    read_operations = ["list_tasks", "get_progress"]
    parameters = [
        ToolParameter(name="operation", type="string", description="One of: create_task, list_tasks, get_progress"),
    ]

    async def execute(self, **kwargs) -> ToolResult:  # noqa: ANN003
        return ToolResult.ok()


def test_enum_restricted_to_read_operations() -> None:
    """When read_operations is set, write operations are excluded from the enum."""
    function = to_openai_function(_ReadWriteTool())["function"]

    assert function["parameters"]["properties"]["operation"]["enum"] == ["list_tasks", "get_progress"]
