"""Compatibility shim — re-exports DomainEvent from the domain layer.

The full event bus infrastructure has been moved to app/_unused/core_events/.
This module is retained only to satisfy existing ``from app.core.events.base
import DomainEvent`` imports in agent modules.
"""

from app.domain.shared.base_event import DomainEvent

__all__ = ["DomainEvent"]
