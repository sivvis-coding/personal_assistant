from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateOne

from app.core.time import utc_now
from app.repositories.base import BaseRepository


class FreshTicketArchiveRepository(BaseRepository):
    """Persist harvested Freshservice tickets for the Insights history archive.

    Parameters:
        database: MongoDB database instance.

    Returns:
        Repository for ``fresh_ticket_archive``.

    Edge cases:
        Keyed by the compound (workspace_id, ticket_id) so tickets from
        different workspaces never collide. Upserts never overwrite an existing
        LLM signature; staleness is detected via signature_source_updated_at.
    """

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        super().__init__(database, "fresh_ticket_archive")

    async def ensure_indexes(self) -> None:
        """Create archive indexes (safe to run repeatedly)."""
        await self.collection.create_index([("workspace_id", 1), ("ticket_id", 1)], unique=True)
        await self.collection.create_index("updated_at_fresh")
        await self.collection.create_index("status")
        await self.collection.create_index("signature")

    def _upsert_op(self, doc: dict[str, Any]) -> UpdateOne:
        """Build an UpdateOne that refreshes ticket data but preserves signature."""
        now = utc_now()
        payload = {k: v for k, v in doc.items() if k not in ("workspace_id", "ticket_id")}
        payload["harvested_at"] = now
        return UpdateOne(
            {"workspace_id": doc["workspace_id"], "ticket_id": doc["ticket_id"]},
            {
                "$set": payload,
                "$setOnInsert": {
                    "signature": None,
                    "signature_source_updated_at": None,
                    "created_at": now,
                },
            },
            upsert=True,
        )

    async def upsert_ticket(self, doc: dict[str, Any]) -> None:
        """Upsert a single archived ticket."""
        await self.collection.bulk_write([self._upsert_op(doc)])

    async def bulk_upsert(self, docs: list[dict[str, Any]]) -> int:
        """Upsert many archived tickets; returns the number processed."""
        if not docs:
            return 0
        await self.collection.bulk_write([self._upsert_op(doc) for doc in docs])
        return len(docs)

    async def find_needing_signature(self, statuses: list[str], limit: int = 200) -> list[dict[str, Any]]:
        """Return archived tickets missing a signature or whose source changed.

        Parameters:
            statuses: Ticket statuses in scope.
            limit: Max tickets to return in one batch.

        Returns:
            Serialized archive documents needing (re)summarization.
        """
        query = {
            "status": {"$in": statuses},
            "$or": [
                {"signature": None},
                {"$expr": {"$ne": ["$signature_source_updated_at", "$updated_at_fresh"]}},
            ],
        }
        cursor = self.collection.find(query).limit(limit)
        return [doc async for doc in _serialized(cursor, self)]

    async def set_signature(
        self, workspace_id: str, ticket_id: str, signature: dict[str, Any], source_updated_at: Any
    ) -> None:
        """Store an LLM signature and record the source version it was built from."""
        await self.collection.update_one(
            {"workspace_id": workspace_id, "ticket_id": ticket_id},
            {"$set": {"signature": signature, "signature_source_updated_at": source_updated_at, "updated_at": utc_now()}},
        )

    async def iter_for_scope(self, statuses: list[str]) -> list[dict[str, Any]]:
        """Return all signed archive documents within the given statuses."""
        query = {"status": {"$in": statuses}, "signature": {"$ne": None}}
        cursor = self.collection.find(query)
        return [doc async for doc in _serialized(cursor, self)]

    async def list_paginated(self, skip: int, limit: int) -> tuple[list[dict[str, Any]], int]:
        """Return a page of archived tickets (newest updated first) and the total count."""
        total = await self.collection.count_documents({})
        cursor = self.collection.find({}).sort("updated_at_fresh", -1).skip(skip).limit(limit)
        items = [doc async for doc in _serialized(cursor, self)]
        return items, total

    async def count(self) -> int:
        """Return the total number of archived tickets."""
        return await self.collection.count_documents({})

    async def count_for_workspace(self, workspace_id: str) -> int:
        """Return the number of archived tickets for a workspace."""
        return await self.collection.count_documents({"workspace_id": workspace_id})


async def _serialized(cursor, repo: BaseRepository):
    """Yield serialized documents from a Motor cursor."""
    async for document in cursor:
        serialized = repo.serialize(document)
        if serialized is not None:
            yield serialized
