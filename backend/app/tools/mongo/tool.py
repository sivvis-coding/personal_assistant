"""Mongo tool implementation."""

from typing import Any

from app.domain.integration_link.value_objects import RelationType
from app.repositories.integration_link_repository import IntegrationLinkRepository
from app.tools.base import ToolInterface, ToolParameter, ToolResult
from app.tools.mongo.adapter import MongoAdapter


class MongoTool(ToolInterface):
    """Tool exposing MongoDB/repository operations to agents.

    Parameters:
        link_repository: Existing integration link repository.

    Returns:
        Mongo tool instance.
    """

    name = "mongo"
    description = "Persist and query integration links and memory."
    parameters = [
        ToolParameter(name="operation", type="string", description="One of: save_link, find_link, find_link_by_target"),
        ToolParameter(name="source_system", type="string", description="Source system name", required=False),
        ToolParameter(name="source_id", type="string", description="Source entity identifier", required=False),
        ToolParameter(name="target_system", type="string", description="Target system name", required=False),
        ToolParameter(name="target_id", type="string", description="Target entity identifier", required=False),
        ToolParameter(name="relation_type", type="string", description="Relation type", required=False, default=RelationType.TICKET_TO_TASK),
    ]

    def __init__(self, link_repository: IntegrationLinkRepository) -> None:
        self._adapter = MongoAdapter(link_repository)

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a Mongo tool operation."""
        operation = kwargs.get("operation")

        try:
            if operation == "save_link":
                source_system = self._require(kwargs, "source_system")
                source_id = self._require(kwargs, "source_id")
                target_system = self._require(kwargs, "target_system")
                target_id = self._require(kwargs, "target_id")
                relation_type = kwargs.get("relation_type", RelationType.TICKET_TO_TASK)
                link_id = await self._adapter.save_link(
                    source_system=source_system,
                    source_id=source_id,
                    target_system=target_system,
                    target_id=target_id,
                    relation_type=relation_type,
                )
                return ToolResult.ok(data={"link_id": link_id}, message=f"Saved link {link_id}")

            if operation == "find_link":
                source_system = self._require(kwargs, "source_system")
                source_id = self._require(kwargs, "source_id")
                relation_type = kwargs.get("relation_type")
                result = await self._adapter.find_link(source_system, source_id, relation_type)
                return ToolResult.ok(data=result, message="Link search completed")

            if operation == "find_link_by_target":
                target_system = self._require(kwargs, "target_system")
                target_id = self._require(kwargs, "target_id")
                relation_type = kwargs.get("relation_type")
                result = await self._adapter.find_link_by_target(target_system, target_id, relation_type)
                return ToolResult.ok(data=result, message="Link search by target completed")

            return ToolResult.error(message=f"Unknown operation '{operation}' for mongo tool")
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(message=str(exc))

    @staticmethod
    def _require(kwargs: dict[str, Any], key: str) -> Any:
        if key not in kwargs or kwargs[key] is None:
            raise ValueError(f"Missing required parameter '{key}'")
        return kwargs[key]
