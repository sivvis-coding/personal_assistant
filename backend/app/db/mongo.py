from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import Settings


class MongoManager:
    """Manage MongoDB client lifecycle.

    Parameters:
        settings: Application settings with Mongo connection values.

    Returns:
        Manager exposing the selected database.

    Edge cases:
        Accessing database before connection raises a runtime error.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: AsyncIOMotorClient | None = None

    async def connect(self) -> None:
        """Open MongoDB connection.

        Parameters:
            None.

        Returns:
            None.

        Edge cases:
            Motor creates connections lazily; ping is done by health endpoint.
        """
        self._client = AsyncIOMotorClient(self._settings.mongo_url)

    async def close(self) -> None:
        """Close MongoDB connection if it exists.

        Parameters:
            None.

        Returns:
            None.

        Edge cases:
            Safe to call before connect.
        """
        if self._client is not None:
            self._client.close()
            self._client = None

    @property
    def database(self) -> AsyncIOMotorDatabase:
        """Return configured MongoDB database.

        Parameters:
            None.

        Returns:
            AsyncIOMotorDatabase instance.

        Edge cases:
            Raises RuntimeError when Mongo has not been connected.
        """
        if self._client is None:
            raise RuntimeError("MongoDB client is not connected")
        return self._client[self._settings.mongo_db_name]
