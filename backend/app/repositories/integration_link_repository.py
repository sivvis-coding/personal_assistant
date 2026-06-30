from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository
from app.schemas.integration import IntegrationLinkDocument


class IntegrationLinkRepository(BaseRepository):
    """Persist relations between external systems.

    Parameters:
        database: MongoDB database instance.

    Returns:
        Repository for `integration_links`.

    Edge cases:
        Existing source-target relations can prevent duplicate external tasks.
    """

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        super().__init__(database, "integration_links")

    async def ensure_indexes(self) -> None:
        """Create indexes for integration link lookup.

        Parameters:
            None.

        Returns:
            None.

        Edge cases:
            Safe to run multiple times.
        """
        await self.collection.create_index([("source_system", 1), ("source_id", 1), ("relation_type", 1)])
        await self.collection.create_index([("target_system", 1), ("target_id", 1)])

    async def save_link(self, link: IntegrationLinkDocument, source: str = "local_assistant") -> str:
        """Save an integration link.

        Parameters:
            link: Link payload.
            source: Source label.

        Returns:
            Stored link ID.

        Edge cases:
            This method does not enforce uniqueness; workflow checks duplicates first.
        """
        return await self.insert_document(link.model_dump(), source=source)

    async def find_link(self, source_system: str, source_id: str, relation_type: str) -> dict[str, Any] | None:
        """Find a link by source entity and relation type.

        Parameters:
            source_system: Source system name.
            source_id: Source entity ID.
            relation_type: Relationship type.

        Returns:
            Serialized link or None.

        Edge cases:
            Used to avoid duplicate ClickUp task creation.
        """
        document = await self.collection.find_one(
            {"source_system": source_system, "source_id": str(source_id), "relation_type": relation_type}
        )
        return self.serialize(document)

    async def find_all_by_relation_type(self, relation_type: str) -> list[dict[str, Any]]:
        """Return all integration links matching a relation type.

        Parameters:
            relation_type: Relationship type to filter by.

        Returns:
            List of serialized link documents.

        Edge cases:
            Returns an empty list when no links exist.
        """
        cursor = self.collection.find({"relation_type": relation_type})
        return [self.serialize(doc) async for doc in cursor if doc is not None]

    async def update_link_status(self, link_id: str, new_status: str) -> None:
        """Persist the latest observed ClickUp task status for a link.

        Parameters:
            link_id: MongoDB ObjectId string of the integration link.
            new_status: New ClickUp task status string.

        Returns:
            None.

        Edge cases:
            Invalid link_id raises ValueError from bson ObjectId parsing.
        """
        await self.update_document(link_id, {"last_known_clickup_status": new_status})
