from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.time import utc_now
from app.repositories.base import BaseRepository


class FreshHarvestStateRepository(BaseRepository):
    """Persist a resumable harvest cursor per Freshservice workspace.

    Parameters:
        database: MongoDB database instance.

    Returns:
        Repository for ``fresh_harvest_state``.

    Edge cases:
        One document per workspace_id; the cursor is checkpointed after each
        page/window so a crashed backfill resumes without re-fetching.
    """

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        super().__init__(database, "fresh_harvest_state")

    async def ensure_indexes(self) -> None:
        """Create the unique workspace_id index."""
        await self.collection.create_index("workspace_id", unique=True)

    async def get(self, workspace_id: str) -> dict[str, Any] | None:
        """Return the harvest state for a workspace, or None when never run."""
        return self.serialize(await self.collection.find_one({"workspace_id": workspace_id}))

    async def upsert(self, workspace_id: str, fields: dict[str, Any]) -> None:
        """Merge fields into the workspace's harvest state."""
        await self.collection.update_one(
            {"workspace_id": workspace_id},
            {"$set": {**fields, "workspace_id": workspace_id, "updated_at": utc_now()}},
            upsert=True,
        )

    async def all(self) -> list[dict[str, Any]]:
        """Return the harvest state for every tracked workspace."""
        items: list[dict[str, Any]] = []
        async for document in self.collection.find({}):
            serialized = self.serialize(document)
            if serialized is not None:
                items.append(serialized)
        return items
