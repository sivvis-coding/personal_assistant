"""ClickUp time tracking tool implementation."""

from typing import Any

from app.tools.base import ToolInterface, ToolParameter, ToolResult
from app.tools.clickup_time_tracking import (
    TimeEntryData,
    build_time_entry_preview,
    get_clickup_client_names,
    prepare_time_entry,
    save_time_entry,
)


class ClickUpTimeTool(ToolInterface):
    """Tool exposing ClickUp time tracking operations to agents.

    This tool wraps the existing LangChain-style time tracking functions
    behind the ToolInterface contract so agents can call them uniformly.

    Parameters:
        None.

    Returns:
        ClickUp time tool instance.
    """

    name = "clickup_time"
    description = "Preview and save ClickUp time entries and list available clients."
    parameters = [
        ToolParameter(name="operation", type="string", description="One of: get_clients, prepare, save"),
        ToolParameter(name="task_name", type="string", description="Task name", required=False),
        ToolParameter(name="description", type="string", description="Work description", required=False),
        ToolParameter(name="start_datetime", type="string", description="Start datetime Europe/Madrid", required=False),
        ToolParameter(name="end_datetime", type="string", description="End datetime Europe/Madrid", required=False),
        ToolParameter(name="client_name", type="string", description="Client name", required=False, default=""),
        ToolParameter(name="approved", type="boolean", description="Approval flag for save", required=False, default=False),
    ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a ClickUp time operation.

        Parameters:
            **kwargs: Operation-specific parameters.

        Returns:
            Tool execution result.
        """
        operation = kwargs.get("operation")

        try:
            if operation == "get_clients":
                names = get_clickup_client_names()
                return ToolResult.ok(data={"clients": names}, message=f"Found {len(names)} client(s)")

            if operation == "prepare":
                time_entry = self._build_time_entry_data(kwargs)
                preview = build_time_entry_preview(time_entry)
                return ToolResult.ok(data=preview, message="Time entry preview ready")

            if operation == "save":
                time_entry = self._build_time_entry_data(kwargs)
                time_entry["approved"] = kwargs.get("approved", False)
                message = save_time_entry(time_entry)
                return ToolResult.ok(data={"message": message}, message=message)

            return ToolResult.error(message=f"Unknown operation '{operation}' for clickup_time tool")
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(message=str(exc))

    @staticmethod
    def _build_time_entry_data(kwargs: dict[str, Any]) -> TimeEntryData:
        """Build TimeEntryData from tool parameters."""
        return TimeEntryData(
            task_name=ClickUpTimeTool._require(kwargs, "task_name"),
            description=ClickUpTimeTool._require(kwargs, "description"),
            start_datetime=ClickUpTimeTool._require(kwargs, "start_datetime"),
            end_datetime=ClickUpTimeTool._require(kwargs, "end_datetime"),
            client_name=kwargs.get("client_name", ""),
        )

    @staticmethod
    def _require(kwargs: dict[str, Any], key: str) -> Any:
        if key not in kwargs or kwargs[key] is None:
            raise ValueError(f"Missing required parameter '{key}'")
        return kwargs[key]
