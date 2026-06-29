from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository
from app.schemas.ai import AiDraftDocument


class AiDraftRepository(BaseRepository):
    """Persist AI-generated drafts.

    Parameters:
        database: MongoDB database instance.

    Returns:
        Repository for `ai_drafts`.

    Edge cases:
        Multiple drafts per ticket and type are allowed for audit history.
    """

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        super().__init__(database, "ai_drafts")

    async def ensure_indexes(self) -> None:
        """Create indexes for AI draft lookup.

        Parameters:
            None.

        Returns:
            None.

        Edge cases:
            Safe to run multiple times.
        """
        await self.collection.create_index([("fresh_ticket_id", 1), ("type", 1), ("created_at", -1)])

    async def save_draft(self, draft: AiDraftDocument, source: str = "openai") -> str:
        """Save an AI draft document.

        Parameters:
            draft: Draft payload.
            source: Source label.

        Returns:
            Stored draft ID.

        Edge cases:
            Pydantic validates draft type before persistence.
        """
        return await self.insert_document(draft.model_dump(), source=source)

    async def find_latest(self, ticket_id: str, draft_type: str) -> dict[str, Any] | None:
        """Find the latest draft for a ticket and type.

        Parameters:
            ticket_id: Fresh ticket identifier.
            draft_type: summary, reply, or user_story.

        Returns:
            Serialized draft or None.

        Edge cases:
            Unknown draft types simply return None.
        """
        document = await self.collection.find_one(
            {"fresh_ticket_id": str(ticket_id), "type": draft_type}, sort=[("created_at", -1)]
        )
        return self.serialize(document)
