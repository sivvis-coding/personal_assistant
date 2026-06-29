from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.core.time import utc_now


class BaseRepository:
    """Provide shared MongoDB repository operations.

    Parameters:
        database: MongoDB database instance.
        collection_name: MongoDB collection name.

    Returns:
        Repository helper bound to a collection.

    Edge cases:
        ObjectId values are converted to strings for API usage.
    """

    def __init__(self, database: AsyncIOMotorDatabase, collection_name: str) -> None:
        self.collection: AsyncIOMotorCollection = database[collection_name]

    async def insert_document(self, payload: dict[str, Any], source: str, metadata: dict[str, Any] | None = None) -> str:
        """Insert a document with standard audit fields.

        Parameters:
            payload: Business document payload.
            source: Document source.
            metadata: Optional contextual metadata.

        Returns:
            Inserted document ID as string.

        Edge cases:
            Existing created_at or updated_at values are overwritten for consistency.
        """
        now = utc_now()
        document = {**payload, "created_at": now, "updated_at": now, "source": source, "metadata": metadata}
        result = await self.collection.insert_one(document)
        return str(result.inserted_id)

    async def update_document(self, document_id: str, payload: dict[str, Any]) -> None:
        """Update a document by ID and refresh updated_at.

        Parameters:
            document_id: MongoDB ObjectId string.
            payload: Fields to set.

        Returns:
            None.

        Edge cases:
            Invalid ObjectId raises ValueError from bson.
        """
        await self.collection.update_one({"_id": ObjectId(document_id)}, {"$set": {**payload, "updated_at": utc_now()}})

    def serialize(self, document: dict[str, Any] | None) -> dict[str, Any] | None:
        """Convert a Mongo document into a JSON-friendly dictionary.

        Parameters:
            document: Mongo document or None.

        Returns:
            Serialized document or None.

        Edge cases:
            Documents without `_id` are returned unchanged except absent ID.
        """
        if document is None:
            return None
        serialized = dict(document)
        if "_id" in serialized:
            serialized["id"] = str(serialized.pop("_id"))
        return serialized
