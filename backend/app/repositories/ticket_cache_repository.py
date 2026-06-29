from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.time import utc_now
from app.repositories.base import BaseRepository
from app.schemas.ticket import Ticket


class TicketCacheRepository(BaseRepository):
    """Persist and retrieve Fresh ticket cache documents.

    Parameters:
        database: MongoDB database instance.

    Returns:
        Repository for `ticket_cache`.

    Edge cases:
        Upserts preserve created_at when a ticket already exists.
    """

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        super().__init__(database, "ticket_cache")

    async def ensure_indexes(self) -> None:
        """Create indexes required by ticket cache queries.

        Parameters:
            None.

        Returns:
            None.

        Edge cases:
            Safe to run multiple times.
        """
        await self.collection.create_index("fresh_ticket_id", unique=True)
        await self.collection.create_index("last_synced_at")

    async def upsert_ticket(self, ticket: Ticket, source: str) -> None:
        """Insert or update a cached ticket.

        Parameters:
            ticket: Normalized ticket.
            source: Integration source.

        Returns:
            None.

        Edge cases:
            Requester is stored as dict for schema flexibility.
        """
        now = utc_now()
        await self.collection.update_one(
            {"fresh_ticket_id": ticket.id},
            {
                "$set": {
                    "subject": ticket.subject,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "requester": ticket.requester.model_dump(),
                    "raw": ticket.raw,
                    "last_synced_at": now,
                    "updated_at": now,
                    "source": source,
                },
                "$setOnInsert": {"created_at": now, "metadata": None},
            },
            upsert=True,
        )

    async def upsert_many(self, tickets: list[Ticket], source: str) -> None:
        """Insert or update multiple cached tickets.

        Parameters:
            tickets: Normalized tickets.
            source: Integration source.

        Returns:
            None.

        Edge cases:
            Empty list performs no writes.
        """
        for ticket in tickets:
            await self.upsert_ticket(ticket, source)

    async def find_by_fresh_ticket_id(self, ticket_id: str) -> dict[str, Any] | None:
        """Find a cached ticket by Fresh ticket ID.

        Parameters:
            ticket_id: Fresh ticket identifier.

        Returns:
            Serialized cached ticket or None.

        Edge cases:
            Ticket IDs are stored as strings for API consistency.
        """
        document = await self.collection.find_one({"fresh_ticket_id": str(ticket_id)})
        return self.serialize(document)
