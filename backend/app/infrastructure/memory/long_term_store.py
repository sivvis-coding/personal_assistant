"""MongoDB-backed long-term memory implementation."""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.memory.interface import LongTermMemory
from app.core.time import utc_now


class MongoLongTermMemory(LongTermMemory):
    """Persistent long-term memory backed by MongoDB.

    Parameters:
        database: MongoDB database instance.
        collection_name: Name of the memory collection.

    Returns:
        Long-term memory instance.

    Edge cases:
        Values are stored as-is, so callers should serialize complex objects.
    """

    def __init__(self, database: AsyncIOMotorDatabase, collection_name: str = "long_term_memory") -> None:
        self._collection = database[collection_name]

    async def store(self, key: str, value: Any, metadata: dict[str, Any] | None = None) -> None:
        """Upsert a memory entry by key."""
        await self._collection.update_one(
            {"key": key},
            {
                "$set": {
                    "value": value,
                    "metadata": metadata or {},
                    "updated_at": utc_now(),
                },
                "$setOnInsert": {"created_at": utc_now()},
            },
            upsert=True,
        )

    async def load(self, key: str) -> Any | None:
        """Load a memory entry by key."""
        document = await self._collection.find_one({"key": key})
        if document is None:
            return None
        return document.get("value")

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search memory by metadata query."""
        mongo_query = {"metadata": query}
        cursor = self._collection.find(mongo_query).limit(100)
        return [{"key": doc["key"], "value": doc.get("value"), "metadata": doc.get("metadata")} async for doc in cursor]

    async def forget(self, key: str) -> None:
        """Remove a memory entry by key."""
        await self._collection.delete_one({"key": key})
