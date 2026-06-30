from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.time import utc_now
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository):
    """Persist assistant conversations and message turns.

    Parameters:
        database: MongoDB database instance.

    Returns:
        Repository for assistant conversations.

    Edge cases:
        Message history is embedded because local conversations are expected to remain small.
    """

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        """Initialize assistant conversation repository.

        Parameters:
            database: MongoDB database instance.

        Returns:
            None.

        Edge cases:
            Collection name is fixed to keep API and index setup aligned.
        """
        super().__init__(database, "assistant_conversations")

    async def ensure_indexes(self) -> None:
        """Create assistant conversation indexes.

        Parameters:
            None.

        Returns:
            None.

        Edge cases:
            Index creation is idempotent.
        """
        await self.collection.create_index("updated_at")

    async def create_conversation(self) -> str:
        """Create an empty assistant conversation.

        Parameters:
            None.

        Returns:
            Conversation document ID.

        Edge cases:
            Source is local because conversations are not synced externally.
        """
        return await self.insert_document({"messages": []}, source="local_assistant")

    async def append_turn(self, conversation_id: str, user_message: str, assistant_answer: str, metadata: dict[str, Any]) -> None:
        """Append a user/assistant turn to a conversation.

        Parameters:
            conversation_id: Conversation document ID.
            user_message: Raw user message.
            assistant_answer: Assistant response text.
            metadata: Additional trace data for audit.

        Returns:
            None.

        Edge cases:
            Invalid IDs raise from the shared update helper.
        """
        turn = {
            "user_message": user_message,
            "assistant_answer": assistant_answer,
            "metadata": metadata,
            "created_at": utc_now(),
        }
        await self.update_document(conversation_id, {"last_message_at": utc_now()})
        await self.collection.update_one({"_id": self._object_id(conversation_id)}, {"$push": {"messages": turn}})

    async def get_pending_state(self, conversation_id: str) -> dict[str, Any] | None:
        """Load pending clarification state for a conversation.

        Parameters:
            conversation_id: Conversation document ID.

        Returns:
            Pending state dictionary or None.

        Edge cases:
            Invalid IDs raise from BSON conversion.
        """
        document = await self.collection.find_one({"_id": self._object_id(conversation_id)}, {"pending_state": 1})
        return document.get("pending_state") if document else None

    async def set_pending_state(self, conversation_id: str, state: dict[str, Any] | None) -> None:
        """Store or clear pending clarification state for a conversation.

        Parameters:
            conversation_id: Conversation document ID.
            state: Pending state to store, or None to clear.

        Returns:
            None.

        Edge cases:
            Passing None removes the field from the document.
        """
        if state is None:
            await self.collection.update_one({"_id": self._object_id(conversation_id)}, {"$unset": {"pending_state": ""}})
        else:
            await self.collection.update_one({"_id": self._object_id(conversation_id)}, {"$set": {"pending_state": state}})

    async def get_messages(self, conversation_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return the most recent conversation turns.

        Parameters:
            conversation_id: Conversation document ID.
            limit: Maximum number of turns to return, ordered from oldest to newest.

        Returns:
            List of turns with user_message, assistant_answer, and metadata.

        Edge cases:
            Invalid IDs raise from BSON conversion.
            Non-existent conversations return an empty list.
        """
        document = await self.collection.find_one(
            {"_id": self._object_id(conversation_id)},
            {"messages": {"$slice": -limit}},
        )
        if document is None:
            return []
        return document.get("messages", [])

    async def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return conversation summaries ordered by most recent activity.

        Uses aggregation pipeline to efficiently get title, message count,
        and timestamps in a single query.

        Parameters:
            limit: Maximum number of conversations to return.

        Returns:
            List of conversation summaries with id, title, message_count, and timestamps.

        Edge cases:
            Empty list when no conversations exist.
        """
        pipeline = [
            {
                "$addFields": {
                    "message_count": {"$size": {"$ifNull": ["$messages", []]}},
                    "first_message": {"$arrayElemAt": ["$messages", 0]},
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "title": {
                        "$cond": {
                            "if": {
                                "$and": [
                                    {"$ne": ["$first_message", None]},
                                    {"$ne": ["$first_message.user_message", None]},
                                    {"$gt": [{"$strLenCP": {"$ifNull": ["$first_message.user_message", ""]}}, 0]},
                                ]
                            },
                            "then": {
                                "$substrCP": [
                                    "$first_message.user_message",
                                    0,
                                    {"$min": [40, {"$strLenCP": {"$ifNull": ["$first_message.user_message", ""]}}]},
                                ]
                            },
                            "else": "Sin título",
                        }
                    },
                    "message_count": 1,
                    "created_at": 1,
                    "updated_at": 1,
                }
            },
            {"$sort": {"updated_at": -1}},
            {"$limit": limit},
        ]

        conversations = []
        async for doc in self.collection.aggregate(pipeline):
            conversations.append({
                "id": str(doc["_id"]),
                "title": doc["title"],
                "message_count": doc["message_count"],
                "updated_at": doc.get("updated_at"),
                "created_at": doc.get("created_at"),
            })
        return conversations

    async def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        """Return a single conversation with all messages.

        Parameters:
            conversation_id: Conversation document ID.

        Returns:
            Conversation document with messages or None if not found.

        Edge cases:
            Invalid IDs raise from BSON conversion.
        """
        document = await self.collection.find_one({"_id": self._object_id(conversation_id)})
        if document is None:
            return None
        serialized = self.serialize(document)
        # Extract title from first user message
        if serialized and serialized.get("messages"):
            messages = serialized["messages"]
            if messages:
                first_user_msg = next((m for m in messages if m.get("user_message")), None)
                if first_user_msg:
                    user_text = first_user_msg["user_message"]
                    serialized["title"] = user_text[:40] + "..." if len(user_text) > 40 else user_text
        return serialized

    def _object_id(self, document_id: str):
        """Convert document ID to ObjectId for embedded update operations.

        Parameters:
            document_id: MongoDB ObjectId string.

        Returns:
            BSON ObjectId.

        Edge cases:
            Invalid IDs raise ValueError from bson.
        """
        from bson import ObjectId

        return ObjectId(document_id)
