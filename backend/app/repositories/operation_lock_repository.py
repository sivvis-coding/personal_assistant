from datetime import timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.time import utc_now
from app.repositories.base import BaseRepository


class OperationLockRepository(BaseRepository):
    """A tiny DB-backed lock to serialize heavy Insights operations.

    Parameters:
        database: MongoDB database instance.

    Returns:
        Repository for ``operation_locks``.

    Edge cases:
        Locks carry a staleness TTL so an operation whose process was killed
        (e.g. a dev hot-reload) does not leave the lock held forever. The app is
        single-process, so a read-then-write acquire is sufficient here (a
        double-clicked trigger is the realistic contention, not true races).
    """

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        super().__init__(database, "operation_locks")

    async def ensure_indexes(self) -> None:
        """Create the unique lock-name index."""
        await self.collection.create_index("name", unique=True)

    async def is_locked(self, name: str, ttl_seconds: int) -> bool:
        """Return whether a fresh (non-stale) lock is currently held.

        Edge cases:
            Motor returns timezone-naive datetimes; normalize to UTC-aware before
            comparing to avoid "can't compare offset-naive and offset-aware".
        """
        doc = await self.collection.find_one({"name": name})
        locked_at = doc.get("locked_at") if doc else None
        if locked_at is None:
            return False
        if locked_at.tzinfo is None:
            locked_at = locked_at.replace(tzinfo=timezone.utc)
        return locked_at > utc_now() - timedelta(seconds=ttl_seconds)

    async def try_acquire(self, name: str, ttl_seconds: int) -> bool:
        """Acquire the lock unless a fresh one is already held.

        Parameters:
            name: Lock name.
            ttl_seconds: A lock older than this is considered stale and reclaimable.

        Returns:
            True when acquired, False when a fresh lock is already held.
        """
        if await self.is_locked(name, ttl_seconds):
            return False
        await self.collection.update_one(
            {"name": name},
            {"$set": {"name": name, "locked_at": utc_now()}},
            upsert=True,
        )
        return True

    async def release(self, name: str) -> None:
        """Release the lock (idempotent)."""
        await self.collection.delete_one({"name": name})
