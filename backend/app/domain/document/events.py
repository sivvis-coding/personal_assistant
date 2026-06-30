"""Document domain events."""

from dataclasses import dataclass

from app.domain.document.value_objects import DocSource, DocType
from app.domain.shared.base_event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class DocumentationGenerated(DomainEvent):
    """Published when documentation is generated automatically.

    Parameters:
        document_id: Internal document identifier.
        source_type: Type of source that generated the document.
        source_id: Identifier of the source entity.
        title: Document title.

    Returns:
        Domain event instance.
    """

    document_id: str
    source_type: str
    source_id: str
    title: str
