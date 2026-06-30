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
        last_known_clickup_status: Last ClickUp task status seen during sync.

    Returns:
        Mongo-ready integration link payload.

    Edge cases:
        target_url may be None when external API omits URLs.
        last_known_clickup_status is None for links created before sync ran.
    """

    source_system: str
    source_id: str
    target_system: str
    target_id: str
    target_url: str | None = None
    relation_type: str
    last_known_clickup_status: str | None = None
