from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.time import utc_now
from app.repositories.base import BaseRepository

# There is a single "current" roadmap per install (personal assistant, one user).
CURRENT_SLUG = "current"


class RoadmapRepository(BaseRepository):
    """Persist the single current roadmap structure.

    Parameters:
        database: MongoDB database instance.

    Returns:
        Repository bound to the ``roadmaps`` collection.

    Edge cases:
        Only the grouping structure is stored (group titles + task IDs), never
        task data; tasks are rehydrated from ClickUp on read so they stay fresh.
    """

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        super().__init__(database, "roadmaps")

    async def ensure_indexes(self) -> None:
        """Create the unique slug index for the singleton roadmap document."""
        await self.collection.create_index("slug", unique=True)

    async def find_current(self) -> dict[str, Any] | None:
        """Return the persisted current roadmap, or None when none exists.

        Parameters:
            None.

        Returns:
            Serialized roadmap document or None.

        Edge cases:
            None is a valid state: the roadmap has never been generated.
        """
        return self.serialize(await self.collection.find_one({"slug": CURRENT_SLUG}))

    async def save_current(self, groups: list[dict[str, Any]], model: str) -> None:
        """Upsert the current roadmap structure.

        Parameters:
            groups: Group structures ({title, summary, task_ids}).
            model: AI model used to (last) generate, or "mock".

        Returns:
            None.

        Edge cases:
            generated_at is preserved on manual saves so it reflects the last AI
            generation, while updated_at always tracks the latest write.
        """
        now = utc_now()
        existing = await self.collection.find_one({"slug": CURRENT_SLUG})
        generated_at = existing.get("generated_at", now) if existing else now
        await self.collection.replace_one(
            {"slug": CURRENT_SLUG},
            {
                "slug": CURRENT_SLUG,
                "groups": groups,
                "model": model,
                "generated_at": generated_at,
                "updated_at": now,
            },
            upsert=True,
        )

    async def touch_generated_at(self) -> None:
        """Mark the current roadmap as freshly AI-generated (set generated_at=now)."""
        await self.collection.update_one(
            {"slug": CURRENT_SLUG},
            {"$set": {"generated_at": utc_now()}},
        )
