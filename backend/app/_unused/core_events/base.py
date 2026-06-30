"""Event bus base types.

Domain events are defined in app.domain.shared.base_event. This module only
provides type aliases and helpers for the event bus layer.
"""

from app.domain.shared.base_event import DomainEvent

__all__ = ["DomainEvent"]
