"""Concrete memory facade implementation."""

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.memory.interface import (
    AgentMemory,
    LongTermMemory,
    MemoryConfig,
    MemoryFacade,
    SemanticMemory,
    ShortTermMemory,
    UserMemory,
)
from app.infrastructure.memory.long_term_store import MongoLongTermMemory
from app.infrastructure.memory.short_term_store import InMemoryShortTermMemory
from app.infrastructure.memory.user_prefs_store import MongoUserMemory


class DefaultMemoryFacade(MemoryFacade):
    """Default memory facade wiring MongoDB and in-memory stores.

    This is a single-user assistant facade.  Only the layers that are
    actually called by agent code are wired by default:
    - long_term  — used by NotificationAgent (store_long)
    - user_prefs — MongoDB preferences store for the assistant user
    - short_term — kept available for event-driven agents; no agent currently
                   calls it in the live path but it is lightweight and free
                   to keep.

    Semantic memory is intentionally omitted: no agent calls upsert_semantic
    or search_semantic in the live path.  The InMemorySemanticMemory
    placeholder has been moved to _unused/.

    Parameters:
        database: MongoDB database instance.
        user_id: Identifier of the assistant user.
        long_term: Optional long-term memory override (for testing).
        user_prefs: Optional user memory override (for testing).

    Returns:
        Memory facade instance.
    """

    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        user_id: str,
        long_term: LongTermMemory | None = None,
        user_prefs: UserMemory | None = None,
    ) -> None:
        self._database = database
        self._user_id = user_id
        self._short_term: ShortTermMemory = InMemoryShortTermMemory()
        self._long_term: LongTermMemory = long_term or MongoLongTermMemory(database)
        self._user_prefs: UserMemory = user_prefs or MongoUserMemory(database, user_id)

    def for_agent(self, agent_id: str) -> AgentMemory:
        """Return an AgentMemory instance scoped to the given agent."""
        return AgentMemory(
            agent_id=agent_id,
            config=MemoryConfig(),
            short_term=self._short_term,
            long_term=self._long_term,
            semantic=None,
            user_prefs=self._user_prefs,
        )
