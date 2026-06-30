"""Memory system interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SearchResult:
    """Result from a semantic memory search.

    Parameters:
        id: Memory entry identifier.
        text: Stored text.
        score: Similarity score (0-1, higher is better).
        metadata: Optional metadata.

    Returns:
        Search result instance.
    """

    id: str
    text: str
    score: float
    metadata: dict[str, Any]


class ShortTermMemory(ABC):
    """Temporary memory scoped to the current conversation or workflow.

    Short-term memory is expected to be fast and ephemeral. Implementations
    may use in-memory stores with TTL.
    """

    @abstractmethod
    async def store(self, conversation_id: str, key: str, value: Any) -> None:
        """Store a value in the conversation context."""

    @abstractmethod
    async def load(self, conversation_id: str, key: str) -> Any | None:
        """Load a value from the conversation context."""

    @abstractmethod
    async def load_all(self, conversation_id: str) -> dict[str, Any]:
        """Load all values for a conversation."""

    @abstractmethod
    async def clear(self, conversation_id: str) -> None:
        """Remove all values for a conversation."""


class LongTermMemory(ABC):
    """Persistent memory for facts and decisions."""

    @abstractmethod
    async def store(self, key: str, value: Any, metadata: dict[str, Any] | None = None) -> None:
        """Persist a value under a key."""

    @abstractmethod
    async def load(self, key: str) -> Any | None:
        """Load a persisted value by key."""

    @abstractmethod
    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search persisted memory by metadata query."""

    @abstractmethod
    async def forget(self, key: str) -> None:
        """Remove a persisted value by key."""


class SemanticMemory(ABC):
    """Vector-based memory for similarity search."""

    @abstractmethod
    async def upsert(self, id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Store or update a text embedding."""

    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Search for the most similar stored texts."""

    @abstractmethod
    async def delete(self, id: str) -> None:
        """Delete a stored embedding by id."""


class UserMemory(ABC):
    """User-specific preferences and settings."""

    @abstractmethod
    async def get_preference(self, key: str) -> Any | None:
        """Load a user preference by key."""

    @abstractmethod
    async def set_preference(self, key: str, value: Any) -> None:
        """Save a user preference."""

    @abstractmethod
    async def get_all(self) -> dict[str, Any]:
        """Load all user preferences."""


@dataclass(frozen=True)
class MemoryConfig:
    """Declarative configuration for an agent's memory needs.

    Parameters:
        short_term: Whether the agent uses conversation context.
        long_term: Whether the agent persists facts.
        semantic: Whether the agent uses vector search.
        user_prefs: Whether the agent reads user preferences.

    Returns:
        Memory configuration.
    """

    short_term: bool = False
    long_term: bool = False
    semantic: bool = False
    user_prefs: bool = False


class MemoryFacade(ABC):
    """Unified facade for all memory layers.

    Agents interact with memory through this facade so they do not need to
    know which storage backend each layer uses.
    """

    @abstractmethod
    def for_agent(self, agent_id: str) -> "AgentMemory": ...


class AgentMemory:
    """Memory API scoped to a single agent."""

    def __init__(
        self,
        agent_id: str,
        config: MemoryConfig,
        short_term: ShortTermMemory | None,
        long_term: LongTermMemory | None,
        semantic: SemanticMemory | None,
        user_prefs: UserMemory | None,
    ) -> None:
        self.agent_id = agent_id
        self.config = config
        self.short_term = short_term
        self.long_term = long_term
        self.semantic = semantic
        self.user_prefs = user_prefs

    async def store_short(self, conversation_id: str, key: str, value: Any) -> None:
        """Store a short-term memory value."""
        if self.short_term is None:
            raise MemoryError(f"Agent {self.agent_id} does not use short-term memory")
        await self.short_term.store(conversation_id, key, value)

    async def load_short(self, conversation_id: str, key: str) -> Any | None:
        """Load a short-term memory value."""
        if self.short_term is None:
            return None
        return await self.short_term.load(conversation_id, key)

    async def store_long(self, key: str, value: Any, metadata: dict[str, Any] | None = None) -> None:
        """Store a long-term memory value."""
        if self.long_term is None:
            raise MemoryError(f"Agent {self.agent_id} does not use long-term memory")
        await self.long_term.store(f"{self.agent_id}:{key}", value, metadata)

    async def load_long(self, key: str) -> Any | None:
        """Load a long-term memory value."""
        if self.long_term is None:
            return None
        return await self.long_term.load(f"{self.agent_id}:{key}")

    async def upsert_semantic(
        self,
        id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Upsert a semantic memory entry."""
        if self.semantic is None:
            raise MemoryError(f"Agent {self.agent_id} does not use semantic memory")
        merged_metadata = {"agent_id": self.agent_id}
        if metadata:
            merged_metadata.update(metadata)
        await self.semantic.upsert(id, text, merged_metadata)

    async def search_semantic(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Search semantic memory."""
        if self.semantic is None:
            return []
        return await self.semantic.search(query, top_k)

    async def get_user_preference(self, key: str) -> Any | None:
        """Load a user preference."""
        if self.user_prefs is None:
            return None
        return await self.user_prefs.get_preference(key)
