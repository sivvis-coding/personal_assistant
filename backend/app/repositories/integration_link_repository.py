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
