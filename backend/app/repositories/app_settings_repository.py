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
