from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MongoDocument(BaseModel):
    """Base schema for persisted MongoDB documents.

    Parameters:
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        source: Origin of the document.
        metadata: Optional contextual data.

    Returns:
        Serializable document model.

    Edge cases:
        Mongo `_id` is stored separately and converted to string by repositories.
    """

    model_config = ConfigDict(populate_by_name=True)

    created_at: datetime
    updated_at: datetime
    source: str
    metadata: dict[str, Any] | None = None


class IdResponse(BaseModel):
    """Represent a created or updated document identifier.

    Parameters:
        id: String representation of MongoDB ObjectId.

    Returns:
        Identifier response.

    Edge cases:
        Empty IDs should never be created by repositories.
    """

    id: str = Field(min_length=1)
