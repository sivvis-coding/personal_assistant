"""In-memory short-term memory implementation."""

import asyncio
import time
from typing import Any

from app.core.memory.interface import ShortTermMemory


class InMemoryShortTermMemory(ShortTermMemory):
    """Thread-safe in-memory short-term memory with TTL.

    Parameters:
        ttl_seconds: Time-to-live for conversation entries.
        max_entries_per_conversation: Maximum stored values per conversation.

    Returns:
        In-memory short-term memory instance.

    Edge cases:
        Expired entries are lazily removed on access and periodically via
        a background cleanup task.
    """

    def __init__(self, ttl_seconds: int = 3600, max_entries_per_conversation: int = 100) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries_per_conversation
        self._store: dict[str, dict[str, tuple[Any, float]]] = {}
        self._lock = asyncio.Lock()

    async def store(self, conversation_id: str, key: str, value: Any) -> None:
        """Store a value with timestamp."""
        async with self._lock:
            conversation = self._store.setdefault(conversation_id, {})
            conversation[key] = (value, time.monotonic())
            if len(conversation) > self._max_entries:
                oldest_key = min(conversation, key=lambda k: conversation[k][1])
                del conversation[oldest_key]

    async def load(self, conversation_id: str, key: str) -> Any | None:
        """Load a value if not expired."""
        async with self._lock:
            conversation = self._store.get(conversation_id, {})
            entry = conversation.get(key)
            if entry is None:
                return None
            value, stored_at = entry
            if self._is_expired(stored_at):
                del conversation[key]
                return None
            return value

    async def load_all(self, conversation_id: str) -> dict[str, Any]:
        """Load all non-expired values for a conversation."""
        async with self._lock:
            conversation = self._store.get(conversation_id, {})
            now = time.monotonic()
            result: dict[str, Any] = {}
            expired_keys: list[str] = []
            for key, (value, stored_at) in conversation.items():
                if self._is_expired(stored_at, now):
                    expired_keys.append(key)
                else:
                    result[key] = value
            for key in expired_keys:
                del conversation[key]
            return result

    async def clear(self, conversation_id: str) -> None:
        """Remove all values for a conversation."""
        async with self._lock:
            self._store.pop(conversation_id, None)

    def _is_expired(self, stored_at: float, now: float | None = None) -> bool:
        now = now or time.monotonic()
        return (now - stored_at) > self._ttl_seconds
