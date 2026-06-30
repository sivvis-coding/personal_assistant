"""Compatibility shim — re-exports DomainEvent from the domain layer.

The event bus, EventRegistry, and EventMiddleware have been moved to
app/_unused/core_events/. Only the DomainEvent type alias is kept here
because agent modules import it from this path.
"""

from app.domain.shared.base_event import DomainEvent

__all__ = ["DomainEvent"]
