"""Base value object primitive."""

from abc import ABC
from dataclasses import dataclass


@dataclass(frozen=True)
class ValueObject(ABC):
    """Immutable domain value object.

    Value objects are identified by their attributes, not by an identity.
    They should be small, immutable, and used to describe characteristics
    of entities and aggregates.
    """
