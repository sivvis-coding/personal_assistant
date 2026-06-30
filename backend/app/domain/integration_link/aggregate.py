"""Integration link aggregate root."""

from dataclasses import dataclass
from datetime import datetime

from app.domain.integration_link.value_objects import RelationType
from app.domain.shared.base_aggregate import AggregateRoot
from app.core.time import utc_now


@dataclass(kw_only=True)
class IntegrationLink(AggregateRoot):
    """Aggregate representing a link between two external systems.

    Integration links decouple agents from knowing how entities relate to
    each other across systems.

    Parameters:
        source_system: Source system name (e.g. freshservice).
        source_id: Source entity identifier.
        target_system: Target system name (e.g. clickup).
        target_id: Target entity identifier.
        relation_type: Type of relationship.
        created_at: When the link was created.

    Returns:
        Integration link aggregate.

    Edge cases:
        Source and target system must differ to avoid self-references.
    """

    source_system: str
    source_id: str
    target_system: str
    target_id: str
    relation_type: str
    created_at: datetime = utc_now()

    def __post_init__(self) -> None:
        if self.source_system == self.target_system:
            raise ValueError("Source and target system must be different")
        if self.source_id == self.target_id and self.source_system == self.target_system:
            raise ValueError("Source and target identifiers must be different")
