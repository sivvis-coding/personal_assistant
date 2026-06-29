from app.core.errors import ExternalServiceError
from app.integrations.fresh import FreshClient, TicketListScope, mock_ticket
from app.repositories.ticket_cache_repository import TicketCacheRepository
from app.schemas.ticket import Ticket, TicketDetailResponse, TicketListResponse, TicketRequester


class TicketService:
    """Coordinate ticket reads across Fresh, cache, and mock fallback.

    Parameters:
        fresh_client: Fresh integration client.
        ticket_cache_repository: Ticket cache repository.

    Returns:
        Service for ticket access.

    Edge cases:
        Cache fallback is used only when Fresh detail fails.
    """

    def __init__(self, fresh_client: FreshClient, ticket_cache_repository: TicketCacheRepository) -> None:
        self._fresh_client = fresh_client
        self._ticket_cache_repository = ticket_cache_repository

    async def list_tickets(self, scope: TicketListScope = "mine") -> TicketListResponse:
        """List tickets and cache them.

        Parameters:
            scope: Ticket visibility scope requested by the caller.

        Returns:
            Ticket list response.

        Edge cases:
            Fresh failures return mock tickets because list has no requested ID for cache fallback.
        """
        try:
            tickets, source = await self._fresh_client.list_tickets(scope)
        except ExternalServiceError:
            tickets, source = [mock_ticket("1001")], "mock"
        await self._ticket_cache_repository.upsert_many(tickets, source)
        return TicketListResponse(items=tickets, source=source, cached=True)

    async def get_ticket(self, ticket_id: str) -> TicketDetailResponse:
        """Get ticket detail from Fresh, cache, or mock fallback.

        Parameters:
            ticket_id: Fresh ticket identifier.

        Returns:
            Ticket detail response.

        Edge cases:
            Cache documents are normalized back into Ticket models.
        """
        try:
            ticket, source = await self._fresh_client.get_ticket(ticket_id)
            await self._ticket_cache_repository.upsert_ticket(ticket, source)
            return TicketDetailResponse(ticket=ticket, source=source)
        except ExternalServiceError:
            cached = await self._ticket_cache_repository.find_by_fresh_ticket_id(ticket_id)
            if cached:
                return TicketDetailResponse(ticket=self._ticket_from_cache(cached), source="cache")
            return TicketDetailResponse(ticket=mock_ticket(ticket_id), source="mock")

    def _ticket_from_cache(self, cached: dict) -> Ticket:
        """Convert a cache document into a Ticket model.

        Parameters:
            cached: Serialized cache document.

        Returns:
            Normalized ticket.

        Edge cases:
            Description may only exist inside raw payload.
        """
        raw = cached.get("raw") or {}
        return Ticket(
            id=str(cached["fresh_ticket_id"]),
            subject=cached.get("subject", "Untitled ticket"),
            status=cached.get("status", "unknown"),
            priority=cached.get("priority", "unknown"),
            requester=TicketRequester.model_validate(cached.get("requester") or {}),
            description=raw.get("description_text") or raw.get("description"),
            raw=raw,
        )
