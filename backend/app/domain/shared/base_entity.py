"""Base entity primitive."""

from abc import ABC
from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass
class Entity(ABC):
    """Base class for domain entities.

    Entities are identified by a unique identity that persists across state
    changes. Equality is based on identity, not attributes.

    Parameters:
        id: Unique identifier. Generated automatically when omitted.

    Returns:
        Domain entity instance.

    Edge cases:
        Two entities with the same id are considered equal even if their
        attributes differ.
    """

    id: UUID = field(default_factory=uuid4)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
