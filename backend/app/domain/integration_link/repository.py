"""Integration link repository interface."""

from abc import ABC, abstractmethod

from app.domain.integration_link.aggregate import IntegrationLink
from app.domain.integration_link.value_objects import RelationType


class IIntegrationLinkRepository(ABC):
    """Abstract repository for integration links.

    Implementations are responsible for persisting links between external
    systems and retrieving them by source or target.
    """

    @abstractmethod
    async def save(self, link: IntegrationLink) -> str:
        """Persist an integration link.

        Parameters:
            link: Integration link to save.

        Returns:
            Internal link identifier.
        """

    @abstractmethod
    async def find_by_source(
        self,
        source_system: str,
        source_id: str,
        relation_type: str | None = None,
    ) -> list[IntegrationLink]:
        """Find links by source system and identifier.

        Parameters:
            source_system: Source system name.
            source_id: Source entity identifier.
            relation_type: Optional relation type filter.

        Returns:
            Matching integration links.
        """

    @abstractmethod
    async def find_by_target(
        self,
        target_system: str,
        target_id: str,
        relation_type: str | None = None,
    ) -> list[IntegrationLink]:
        """Find links by target system and identifier.

        Parameters:
            target_system: Target system name.
            target_id: Target entity identifier.
            relation_type: Optional relation type filter.

        Returns:
            Matching integration links.
        """
