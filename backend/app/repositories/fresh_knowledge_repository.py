from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.time import utc_now
from app.repositories.base import BaseRepository

# Single knowledge base per install (one user), mirroring RoadmapRepository.
CURRENT_SLUG = "current"


class FreshKnowledgeRepository(BaseRepository):
    """Persist the generated Freshservice knowledge base (themes + recurring bugs).

    Parameters:
        database: MongoDB database instance.

    Returns:
        Repository for ``fresh_knowledge``.

    Edge cases:
        A single document keyed by slug="current"; regeneration replaces it.
    """

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        super().__init__(database, "fresh_knowledge")

    async def ensure_indexes(self) -> None:
        """Create the unique slug index for the singleton knowledge document."""
        await self.collection.create_index("slug", unique=True)

    async def get_current(self) -> dict[str, Any] | None:
        """Return the persisted knowledge base, or None when never generated."""
        return self.serialize(await self.collection.find_one({"slug": CURRENT_SLUG}))

    async def save_current(self, departments: list[dict[str, Any]], model: str) -> None:
        """Replace the current knowledge base document (analysis split by department)."""
        now = utc_now()
        await self.collection.replace_one(
            {"slug": CURRENT_SLUG},
            {
                "slug": CURRENT_SLUG,
                "departments": departments,
                "model": model,
                "generated_at": now,
                "updated_at": now,
            },
            upsert=True,
        )
