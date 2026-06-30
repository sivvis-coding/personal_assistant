"""In-memory semantic memory implementation — UNUSED.

This module has been moved out of the active code path because no agent
calls upsert_semantic or search_semantic in the live path (chat API or
event-driven orchestrator).

If a concrete use case for semantic/vector search arises in the future,
this placeholder keyword-based implementation should be replaced with a
real vector database (ChromaDB, Qdrant, etc.) before re-enabling.

Original location: app/infrastructure/memory/semantic_store.py
Moved in: Step 7 (trim memory to what's actually used)
"""

from typing import Any

from app.core.memory.interface import SearchResult, SemanticMemory


class InMemorySemanticMemory(SemanticMemory):
    """Simple in-memory semantic memory.

    Parameters:
        max_entries: Maximum number of entries to keep in memory.

    Returns:
        In-memory semantic memory instance.

    Edge cases:
        Search uses keyword overlap as a crude similarity score. This is
        intentionally simple for Phase 1.
    """

    def __init__(self, max_entries: int = 1000) -> None:
        self._entries: dict[str, tuple[str, dict[str, Any]]] = {}
        self._max_entries = max_entries

    async def upsert(self, id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Store or update an entry."""
        if len(self._entries) >= self._max_entries and id not in self._entries:
            oldest_id = next(iter(self._entries))
            del self._entries[oldest_id]
        self._entries[id] = (text, metadata or {})

    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Search entries by keyword overlap."""
        query_terms = set(query.lower().split())
        if not query_terms:
            return []

        scored: list[tuple[str, str, float, dict[str, Any]]] = []
        for entry_id, (text, metadata) in self._entries.items():
            text_terms = set(text.lower().split())
            overlap = query_terms & text_terms
            if not overlap:
                continue
            score = len(overlap) / len(query_terms)
            scored.append((entry_id, text, score, metadata))

        scored.sort(key=lambda item: item[2], reverse=True)
        return [
            SearchResult(id=entry_id, text=text, score=score, metadata=metadata)
            for entry_id, text, score, metadata in scored[:top_k]
        ]

    async def delete(self, id: str) -> None:
        """Delete an entry by id."""
        self._entries.pop(id, None)
