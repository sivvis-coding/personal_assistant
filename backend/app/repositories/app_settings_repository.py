from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class AppSettingsRepository(BaseRepository):
    """Persist application settings for future local configuration.

    Parameters:
        database: MongoDB database instance.

    Returns:
        Repository for `app_settings`.

    Edge cases:
        Not used by V1 workflows, but collection is prepared.
    """

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        super().__init__(database, "app_settings")

    async def ensure_indexes(self) -> None:
        """Create unique key index for app settings.

        Parameters:
            None.

        Returns:
            None.

        Edge cases:
            Safe to run multiple times.
        """
        await self.collection.create_index("key", unique=True)

    async def get_all(self) -> dict[str, Any]:
        """Return all stored settings as a dictionary.

        Parameters:
            None.

        Returns:
            Dictionary of setting key to value.

        Edge cases:
            Empty collection returns an empty dictionary.
        """
        settings: dict[str, Any] = {}
        async for document in self.collection.find({}):
            serialized = self.serialize(document)
            if serialized:
                settings[serialized["key"]] = serialized["value"]
        return settings

    async def get(self, key: str, default: Any = None) -> Any:
        """Return a single setting value.

        Parameters:
            key: Setting key.
            default: Value to return when the key is missing.

        Returns:
            Stored value or default.
        """
        document = await self.collection.find_one({"key": key})
        serialized = self.serialize(document)
        return serialized["value"] if serialized else default

    async def set(self, key: str, value: Any) -> None:
        """Store or update a setting value.

        Parameters:
            key: Setting key.
            value: Setting value.

        Returns:
            None.

        Edge cases:
            Empty string values are stored explicitly.
        """
        await self.collection.update_one(
            {"key": key},
            {"$set": {"key": key, "value": value}},
            upsert=True,
        )
