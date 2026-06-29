from pydantic import BaseModel


class IntegrationLinkDocument(BaseModel):
    """Represent a relation between external systems.

    Parameters:
        source_system: Source system name.
        source_id: Source entity ID.
        target_system: Target system name.
        target_id: Target entity ID.
        target_url: Target entity URL.
        relation_type: Relationship type.

    Returns:
        Mongo-ready integration link payload.

    Edge cases:
        target_url may be None when external API omits URLs.
    """

    source_system: str
    source_id: str
    target_system: str
    target_id: str
    target_url: str | None = None
    relation_type: str
