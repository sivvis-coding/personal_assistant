"""Shared domain primitives used by all aggregates."""

from app.domain.shared.base_aggregate import AggregateRoot
from app.domain.shared.base_entity import Entity
from app.domain.shared.base_event import DomainEvent, EventMetadata
from app.domain.shared.base_value_object import ValueObject

__all__ = [
    "AggregateRoot",
    "DomainEvent",
    "Entity",
    "EventMetadata",
    "ValueObject",
]