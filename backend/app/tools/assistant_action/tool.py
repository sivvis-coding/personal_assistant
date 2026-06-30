"""Assistant action tool implementation."""

from typing import Any

from app.assistant.schemas.actions import AssistantActionCreate
from app.repositories.assistant_action_repository import AssistantActionRepository
from app.tools.base import ToolInterface, ToolParameter, ToolResult


class AssistantActionTool(ToolInterface):
    """Tool for creating and querying assistant actions.

    This tool allows agents to propose actions that require human approval
    before execution.

    Parameters:
        repository: Assistant action repository.

    Returns:
        Assistant action tool instance.
    """

    name = "assistant_action"
    description = "Create pending assistant actions that require human approval."
    parameters = [
        ToolParameter(name="operation", type="string", description="One of: create, list_pending"),
        ToolParameter(name="action_type", type="string", description="Action type", required=False),
        ToolParameter(name="title", type="string", description="Action title", required=False),
        ToolParameter(name="description", type="string", description="Action description", required=False),
        ToolParameter(name="payload", type="object", description="Action payload", required=False, default={}),
        ToolParameter(name="ticket_id", type="string", description="Optional ticket id", required=False, default=None),
    ]

    def __init__(self, repository: AssistantActionRepository) -> None:
        self._repository = repository

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute an assistant action operation."""
        operation = kwargs.get("operation")

        try:
            if operation == "create":
                action_type = self._require(kwargs, "action_type")
                title = self._require(kwargs, "title")
                description = self._require(kwargs, "description")
                payload = kwargs.get("payload", {})
                ticket_id = kwargs.get("ticket_id")

                action_create = AssistantActionCreate(
                    action_type=action_type,
                    title=title,
                    description=description,
                    payload=payload,
                    ticket_id=ticket_id,
                )
                action = await self._repository.create_action(action_create)
                return ToolResult.ok(
                    data=action.model_dump(),
                    message=f"Created assistant action {action.id}",
                )

            if operation == "list_pending":
                actions = await self._repository.list_pending()
                return ToolResult.ok(
                    data={"actions": [action.model_dump() for action in actions]},
                    message=f"Found {len(actions)} pending action(s)",
                )

            return ToolResult.error(message=f"Unknown operation '{operation}' for assistant_action tool")
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(message=str(exc))

    @staticmethod
    def _require(kwargs: dict[str, Any], key: str) -> Any:
        if key not in kwargs or kwargs[key] is None:
            raise ValueError(f"Missing required parameter '{key}'")
        return kwargs[key]
