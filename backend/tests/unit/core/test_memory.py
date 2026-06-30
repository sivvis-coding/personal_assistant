"""Tests for the memory system."""

import pytest

from app.core.memory.interface import AgentMemory, MemoryConfig
from app.infrastructure.memory.long_term_store import MongoLongTermMemory
from app.infrastructure.memory.short_term_store import InMemoryShortTermMemory
from app.infrastructure.memory.user_prefs_store import MongoUserMemory


class FakeDatabase:
    """In-memory database that mimics Motor's collection interface."""

    def __init__(self) -> None:
        self._collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> "FakeCollection":
        if name not in self._collections:
            self._collections[name] = FakeCollection()
        return self._collections[name]


class FakeCollection:
    """In-memory MongoDB collection for testing."""

    def __init__(self) -> None:
        self._documents: dict[str, dict] = {}
        self._id_counter = 0

    async def update_one(self, query: dict, update: dict, upsert: bool = False) -> None:
        key = query.get("key") or query.get("user_id")
        existing = self._documents.get(key, {})

        if "$set" in update:
            for dotted_key, value in update["$set"].items():
                self._set_dotted(existing, dotted_key, value)
        if "$setOnInsert" in update and key not in self._documents:
            for dotted_key, value in update["$setOnInsert"].items():
                self._set_dotted(existing, dotted_key, value)

        self._documents[key] = existing

    def _set_dotted(self, document: dict, dotted_key: str, value: object) -> None:
        parts = dotted_key.split(".")
        current = document
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    async def find_one(self, query: dict) -> dict | None:
        key = query.get("key") or query.get("user_id")
        return self._documents.get(key)

    async def delete_one(self, query: dict) -> None:
        key = query.get("key")
        self._documents.pop(key, None)

    async def find(self, query: dict):
        for document in self._documents.values():
            yield document


@pytest.mark.asyncio
async def test_short_term_memory_stores_and_loads_values():
    """Short-term memory should retain values within TTL."""
    memory = InMemoryShortTermMemory(ttl_seconds=60)

    await memory.store("conv-1", "intent", "track_time")
    value = await memory.load("conv-1", "intent")

    assert value == "track_time"


@pytest.mark.asyncio
async def test_short_term_memory_expires_values():
    """Short-term memory should evict values after TTL."""
    memory = InMemoryShortTermMemory(ttl_seconds=0)

    await memory.store("conv-1", "intent", "track_time")
    value = await memory.load("conv-1", "intent")

    assert value is None


@pytest.mark.asyncio
async def test_long_term_memory_persists_values():
    """Long-term memory should persist key-value pairs."""
    db = FakeDatabase()
    memory = MongoLongTermMemory(db)

    await memory.store("ticket:42", {"status": "open"})
    value = await memory.load("ticket:42")

    assert value == {"status": "open"}


@pytest.mark.asyncio
async def test_user_memory_stores_preferences():
    """User memory should store and retrieve preferences."""
    db = FakeDatabase()
    memory = MongoUserMemory(db, user_id="ivan")

    await memory.set_preference("language", "es")
    value = await memory.get_preference("language")

    assert value == "es"


@pytest.mark.asyncio
async def test_agent_memory_scopes_keys_by_agent():
    """Agent memory should prefix long-term keys with the agent id."""
    db = FakeDatabase()
    facade_memory = MongoLongTermMemory(db)
    agent_memory = AgentMemory(
        agent_id="freshservice",
        config=MemoryConfig(long_term=True),
        short_term=None,
        long_term=facade_memory,
        semantic=None,
        user_prefs=None,
    )

    await agent_memory.store_long("context", {"ticket_id": "42"})
    value = await agent_memory.load_long("context")

    assert value == {"ticket_id": "42"}
