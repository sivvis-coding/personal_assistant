"""MongoDB-backed user preferences implementation."""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.memory.interface import UserMemory
from app.core.time import utc_now


class MongoUserMemory(UserMemory):
    """Persistent user preferences backed by MongoDB.

    Parameters:
        database: MongoDB database instance.
        collection_name: Name of the preferences collection.
        user_id: Identifier of the user whose preferences are stored.

    Returns:
        User memory instance.

    Edge cases:
        A single document per user is used to keep preferences atomic.
    """

    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        user_id: str,
        collection_name: str = "user_preferences",
    ) -> None:
        self._collection = database[collection_name]
        self._user_id = user_id

    async def get_preference(self, key: str) -> Any | None:
        """Load a single user preference by key."""
        document = await self._collection.find_one({"user_id": self._user_id})
        if document is None:
            return None
        return document.get("preferences", {}).get(key)

    async def set_preference(self, key: str, value: Any) -> None:
        """Save a single user preference."""
        await self._collection.update_one(
            {"user_id": self._user_id},
            {
                "$set": {
                    f"preferences.{key}": value,
                    "updated_at": utc_now(),
                },
                "$setOnInsert": {"created_at": utc_now()},
            },
            upsert=True,
        )

    async def get_all(self) -> dict[str, Any]:
        """Load all user preferences."""
        document = await self._collection.find_one({"user_id": self._user_id})
        if document is None:
            return {}
        return dict(document.get("preferences", {}))
