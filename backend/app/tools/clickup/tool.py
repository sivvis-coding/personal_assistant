"""ClickUp tool implementation."""

from typing import Any

from app.integrations.clickup import ClickUpClient
from app.tools.base import ToolInterface, ToolParameter, ToolResult
from app.tools.clickup.adapter import ClickUpAdapter
from app.tools.clickup.schemas import (
    CreateTaskInput,
    GetProgressInput,
    ListTasksInput,
    ReadCommentsInput,
    UpdateTaskInput,
)


class ClickUpTool(ToolInterface):
    """Tool exposing ClickUp operations to agents.

    Parameters:
        client: Existing ClickUpClient instance.

    Returns:
        ClickUp tool instance.
    """

    name = "clickup"
    description = "Create, update and read ClickUp tasks."
    parameters = [
        ToolParameter(name="operation", type="string", description="One of: create_task, update_task, list_tasks, get_progress, read_comments"),
        ToolParameter(name="ticket_id", type="string", description="Source ticket identifier", required=False),
        ToolParameter(name="task_id", type="string", description="ClickUp task identifier", required=False),
        ToolParameter(name="title", type="string", description="Task title", required=False),
        ToolParameter(name="description", type="string", description="Task description", required=False),
        ToolParameter(name="changes", type="object", description="Fields to update", required=False),
    ]

    def __init__(self, client: ClickUpClient) -> None:
        self._adapter = ClickUpAdapter(client)

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a ClickUp operation."""
        operation = kwargs.get("operation")

        try:
            if operation == "create_task":
                ticket_id = self._require(kwargs, "ticket_id")
                title = self._require(kwargs, "title")
                result = await self._adapter.create_task(
                    CreateTaskInput(
                        ticket_id=ticket_id,
                        title=title,
                        description=kwargs.get("description"),
                    )
                )
                return ToolResult.ok(data=result, message=f"Created ClickUp task {result.id}")

            if operation == "update_task":
                task_id = self._require(kwargs, "task_id")
                changes = kwargs.get("changes", {})
                data = await self._adapter.update_task(UpdateTaskInput(task_id=task_id, changes=changes))
                return ToolResult.ok(data=data, message=f"Updated ClickUp task {task_id}")

            if operation == "list_tasks":
                data = await self._adapter.list_tasks(ListTasksInput())
                return ToolResult.ok(data=data, message=f"Listed {len(data['tasks'])} tasks from {data['source']}")

            if operation == "get_progress":
                task_id = self._require(kwargs, "task_id")
                data = await self._adapter.get_progress(GetProgressInput(task_id=task_id))
                return ToolResult.ok(data=data, message=f"Retrieved progress for task {task_id}")

            if operation == "read_comments":
                task_id = self._require(kwargs, "task_id")
                data = await self._adapter.read_comments(ReadCommentsInput(task_id=task_id))
                return ToolResult.ok(data=data, message=f"Read comments for task {task_id}")

            return ToolResult.error(message=f"Unknown operation '{operation}' for clickup tool")
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(message=str(exc))

    @staticmethod
    def _require(kwargs: dict[str, Any], key: str) -> Any:
        if key not in kwargs or kwargs[key] is None:
            raise ValueError(f"Missing required parameter '{key}'")
        return kwargs[key]
