from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.assistant.schemas.actions import AssistantAction, AssistantActionCreate
from app.repositories.base import BaseRepository


class AssistantActionRepository(BaseRepository):
    """Persist assistant actions that need approval or audit.

    Parameters:
        database: MongoDB database instance.

    Returns:
        Repository for assistant action records.

    Edge cases:
        Actions are append-only in intent but status/result can change during execution.
    """

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        """Initialize assistant action repository.

        Parameters:
            database: MongoDB database instance.

        Returns:
            None.

        Edge cases:
            Collection name is fixed because actions are audited separately from workflow runs.
        """
        super().__init__(database, "assistant_actions")

    async def ensure_indexes(self) -> None:
        """Create assistant action indexes.

        Parameters:
            None.

        Returns:
            None.

        Edge cases:
            Safe to run repeatedly during app startup.
        """
        await self.collection.create_index([("status", 1), ("created_at", -1)])
        await self.collection.create_index([("ticket_id", 1), ("action_type", 1)])

    async def create_action(self, action: AssistantActionCreate) -> AssistantAction:
        """Persist a proposed assistant action.

        Parameters:
            action: Action creation payload.

        Returns:
            Stored assistant action.

        Edge cases:
            New actions always start as proposed.
        """
        action_id = await self.insert_document({**action.model_dump(), "status": "proposed", "result": None}, source="assistant")
        stored = await self.get_action(action_id)
        if stored is None:
            raise RuntimeError("Assistant action was not stored")
        return stored

    async def get_action(self, action_id: str) -> AssistantAction | None:
        """Load one assistant action.

        Parameters:
            action_id: Action document ID.

        Returns:
            Assistant action or None.

        Edge cases:
            Invalid ObjectId values raise from BSON conversion.
        """
        document = await self.collection.find_one({"_id": ObjectId(action_id)})
        serialized = self.serialize(document)
        return self._to_action(serialized) if serialized else None

    async def count_pending(self) -> int:
        """Count actions waiting for user approval.

        Parameters:
            None.

        Returns:
            Number of proposed assistant actions.

        Edge cases:
            Completed, rejected, and failed actions are excluded.
        """
        return await self.collection.count_documents({"status": "proposed"})

    async def list_pending(self) -> list[AssistantAction]:
        """List actions waiting for user approval.

        Parameters:
            None.

        Returns:
            Proposed assistant actions ordered newest first.

        Edge cases:
            Completed, rejected, and failed actions are excluded.
        """
        cursor = self.collection.find({"status": "proposed"}).sort("created_at", -1)
        actions: list[AssistantAction] = []
        async for document in cursor:
            serialized = self.serialize(document)
            if serialized is not None:
                actions.append(self._to_action(serialized))
        return actions

    async def update_payload(self, action_id: str, payload: dict[str, Any]) -> AssistantAction:
        """Update the payload of a proposed action before approval.

        Parameters:
            action_id: Action document ID.
            payload: New payload to store.

        Returns:
            Updated assistant action.

        Edge cases:
            Only proposed actions should be updated; callers enforce this.
        """
        await self.update_document(action_id, {"payload": payload})
        updated = await self.get_action(action_id)
        if updated is None:
            raise RuntimeError("Assistant action disappeared during payload update")
        return updated

    async def update_status(self, action_id: str, status: str, result: dict[str, Any] | None = None) -> AssistantAction:
        """Update action status and optional result.

        Parameters:
            action_id: Action document ID.
            status: New action status.
            result: Optional execution result.

        Returns:
            Updated assistant action.

        Edge cases:
            Missing action raises RuntimeError because API layer should load first.
        """
        payload: dict[str, Any] = {"status": status}
        if result is not None:
            payload["result"] = result
        await self.update_document(action_id, payload)
        updated = await self.get_action(action_id)
        if updated is None:
            raise RuntimeError("Assistant action disappeared during update")
        return updated

    def _to_action(self, document: dict[str, Any]) -> AssistantAction:
        """Convert serialized Mongo document into an AssistantAction model.

        Parameters:
            document: Serialized action document.

        Returns:
            Assistant action model.

        Edge cases:
            Extra Mongo audit fields are ignored by Pydantic.
        """
        return AssistantAction.model_validate(document)
