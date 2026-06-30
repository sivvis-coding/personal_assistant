"""Adapter exposing MongoDB/repository capabilities as tool operations."""

from typing import Any

from app.domain.integration_link.value_objects import RelationType
from app.repositories.integration_link_repository import IntegrationLinkRepository
from app.schemas.integration import IntegrationLinkDocument


class MongoAdapter:
    """Thin adapter around repositories and memory stores.

    Parameters:
        link_repository: Existing integration link repository.

    Returns:
        Adapter instance.
    """

    def __init__(self, link_repository: IntegrationLinkRepository) -> None:
        self._link_repository = link_repository

    async def save_link(
        self,
        source_system: str,
        source_id: str,
        target_system: str,
        target_id: str,
        relation_type: str,
    ) -> str:
        """Save an integration link between two systems."""
        link = IntegrationLinkDocument(
            source_system=source_system,
            source_id=source_id,
            target_system=target_system,
            target_id=target_id,
            target_url=None,
            relation_type=relation_type,
        )
        return await self._link_repository.save_link(link)

    async def find_link(
        self,
        source_system: str,
        source_id: str,
        relation_type: str | None = None,
    ) -> dict[str, Any] | None:
        """Find an integration link by source and optional relation type."""
        if relation_type is None:
            relation_type = RelationType.TICKET_TO_TASK
        return await self._link_repository.find_link(source_system, source_id, relation_type)

    async def find_link_by_target(
        self,
        target_system: str,
        target_id: str,
        relation_type: str | None = None,
    ) -> dict[str, Any] | None:
        """Find an integration link by target and optional relation type."""
        if relation_type is None:
            relation_type = RelationType.TICKET_TO_TASK
        return await self._link_repository.find_link(target_system, target_id, relation_type)
