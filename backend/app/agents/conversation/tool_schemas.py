"""Build OpenAI native function-calling schemas from ToolInterface definitions.

The conversation agent exposes each registered tool to the model as a native
function. The valid ``operation`` values are declared in each tool's
``operation`` parameter description using the convention ``"One of: a, b, c"``;
this module turns that convention into a JSON-Schema ``enum`` so the model can
only pick a real operation.
"""

import re
from typing import Any

from app.tools.base import ToolInterface, ToolParameter

_JSON_TYPES = {"string", "boolean", "integer", "number", "object", "array"}
_OPERATION_RE = re.compile(r"one of:\s*(.+)", re.IGNORECASE)


def _parse_operation_enum(description: str) -> list[str]:
    """Extract the operation enum from a ``"One of: a, b, c"`` description."""
    match = _OPERATION_RE.search(description)
    if not match:
        return []
    return [op.strip() for op in re.split(r"[,/]", match.group(1)) if op.strip()]


def _parameter_schema(param: ToolParameter, operation_enum: list[str]) -> dict[str, Any]:
    """Build the JSON-Schema fragment for a single tool parameter."""
    json_type = param.type if param.type in _JSON_TYPES else "string"
    schema: dict[str, Any] = {"type": json_type, "description": param.description}
    if json_type == "object":
        schema["additionalProperties"] = True
    if param.name == "operation" and operation_enum:
        schema["enum"] = operation_enum
    return schema


def to_openai_function(tool: ToolInterface) -> dict[str, Any]:
    """Convert a ToolInterface into an OpenAI function-calling tool schema.

    The exposed ``operation`` enum is restricted to the tool's ``read_operations``
    when defined, so the conversation agent can only invoke read operations;
    otherwise the enum is parsed from the operation parameter's description.
    """
    operation_enum = list(getattr(tool, "read_operations", []) or [])
    if not operation_enum:
        description = next((p.description for p in tool.parameters if p.name == "operation"), "")
        operation_enum = _parse_operation_enum(description)
    properties = {param.name: _parameter_schema(param, operation_enum) for param in tool.parameters}
    required = [param.name for param in tool.parameters if param.required]
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def build_tool_schemas(tools: list[ToolInterface]) -> list[dict[str, Any]]:
    """Convert a list of tools into OpenAI function-calling schemas."""
    return [to_openai_function(tool) for tool in tools]
