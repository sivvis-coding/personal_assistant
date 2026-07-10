from datetime import datetime, timedelta

from app.core.time import utc_now
from app.repositories.operation_lock_repository import OperationLockRepository


class FakeCollection:
    """Minimal in-memory stand-in for the Motor collection (single lock doc)."""

    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    async def find_one(self, query):
        return self.docs.get(query["name"])

    async def update_one(self, query, update, upsert=False):
        name = query["name"]
        # Mongo/Motor stores and returns timezone-naive datetimes; mimic that so
        # naive/aware comparison bugs are caught here.
        fields = {k: (v.replace(tzinfo=None) if isinstance(v, datetime) else v) for k, v in update["$set"].items()}
        self.docs[name] = {**self.docs.get(name, {}), **fields}

    async def delete_one(self, query):
        self.docs.pop(query["name"], None)

    async def create_index(self, *a, **k):
        return None


class FakeDB:
    def __init__(self) -> None:
        self._coll = FakeCollection()

    def __getitem__(self, _name):
        return self._coll


def _repo() -> OperationLockRepository:
    return OperationLockRepository(FakeDB())


async def test_acquire_then_busy_then_release():
    repo = _repo()
    assert await repo.try_acquire("insights", 3600) is True
    # A second acquire while held is rejected.
    assert await repo.try_acquire("insights", 3600) is False
    assert await repo.is_locked("insights", 3600) is True
    await repo.release("insights")
    assert await repo.is_locked("insights", 3600) is False
    # Re-acquirable after release.
    assert await repo.try_acquire("insights", 3600) is True


async def test_stale_lock_is_reclaimable():
    repo = _repo()
    assert await repo.try_acquire("insights", 3600) is True
    # Simulate a lock left behind ~2h ago by a killed process.
    repo.collection.docs["insights"]["locked_at"] = utc_now() - timedelta(hours=2)
    assert await repo.is_locked("insights", 3600) is False  # older than 1h TTL → stale
    assert await repo.try_acquire("insights", 3600) is True  # reclaimed


async def test_release_is_idempotent():
    repo = _repo()
    await repo.release("insights")  # no lock held — must not raise
    assert await repo.try_acquire("insights", 3600) is True
