from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.core.errors import ExternalServiceError
from app.integrations.fresh import FreshClient, TicketListScope, mock_ticket
from app.repositories.ticket_cache_repository import TicketCacheRepository
from app.schemas.ticket import Ticket, TicketConversationsResponse, TicketDetailResponse, TicketListResponse, TicketRequester
from app.services import sla as sla_module

logger = logging.getLogger(__name__)


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

    LIST_CACHE_TTL_SECONDS = 60

    def __init__(self, fresh_client: FreshClient, ticket_cache_repository: TicketCacheRepository) -> None:
        self._fresh_client = fresh_client
        self._ticket_cache_repository = ticket_cache_repository
        self._list_cache: tuple[str, datetime, TicketListResponse] | None = None
        self._list_lock = asyncio.Lock()
        self._list_pending: asyncio.Future[tuple[list[Ticket], str]] | None = None

    @staticmethod
    def _enrich_ticket(ticket: Ticket, now: datetime) -> Ticket:
        """Return a copy of ticket enriched with computed sla and overdue fields.

        Parameters:
            ticket: Normalized ticket to enrich.
            now: Current UTC time used for SLA computation.

        Returns:
            New Ticket instance with sla and overdue populated.

        Edge cases:
            Raw cache documents are not modified — enrichment is applied only to
            in-memory Ticket objects before they are returned to callers.
        """
        sla_hint = sla_module.compute_sla(ticket, now)
        overdue = sla_module.is_overdue(ticket, now)
        return ticket.model_copy(update={"sla": sla_hint, "overdue": overdue})

    async def list_tickets(
        self, scope: TicketListScope = "mine", *, include_closed: bool = False
    ) -> TicketListResponse:
        """List tickets and cache them.

        Parameters:
            scope: Ticket visibility scope requested by the caller.
            include_closed: Whether to include closed tickets in the result.

        Returns:
            Ticket list response.

        Edge cases:
            When Fresh credentials are configured, errors are raised instead of silently returning mock data.
        """
        cache_key = f"{scope}|closed={include_closed}"
        if self._list_cache is not None:
            cached_key, cached_at, cached_response = self._list_cache
            if cached_key == cache_key and cached_at + timedelta(seconds=self.LIST_CACHE_TTL_SECONDS) >= datetime.now(timezone.utc):
                logger.info("Cache HIT for key: %s", cache_key)
                return cached_response.model_copy(update={"source": "cache"})

        logger.info("Cache MISS for key: %s, calling Freshservice", cache_key)
        async with self._list_lock:
            if self._list_cache is not None:
                cached_key, cached_at, cached_response = self._list_cache
                if cached_key == cache_key and cached_at + timedelta(seconds=self.LIST_CACHE_TTL_SECONDS) >= datetime.now(timezone.utc):
                    logger.info("Cache HIT for key: %s", cache_key)
                    return cached_response.model_copy(update={"source": "cache"})
            if self._list_pending is not None:
                tickets, source = await self._list_pending
            else:
                self._list_pending = asyncio.get_event_loop().create_future()
                try:
                    tickets, source = await self._fresh_client.list_tickets(scope)
                    self._list_pending.set_result((tickets, source))
                except Exception as exc:
                    if isinstance(exc, ExternalServiceError):
                        logger.error("Fresh list tickets failed: %s", exc)
                    self._list_pending.set_exception(exc)
                    raise
                finally:
                    self._list_pending = None

            if not include_closed:
                tickets = [t for t in tickets if t.status not in {"closed", "resolved"}]

            now = datetime.now(timezone.utc)
            tickets = [self._enrich_ticket(t, now) for t in tickets]

            await self._ticket_cache_repository.upsert_many(tickets, source)
            response = TicketListResponse(items=tickets, source=source, cached=True)
            self._list_cache = (cache_key, datetime.now(timezone.utc), response)
            return response

    async def get_ticket(self, ticket_id: str) -> TicketDetailResponse:
        """Get ticket detail from Fresh, cache, or mock fallback.

        Parameters:
            ticket_id: Fresh ticket identifier.

        Returns:
            Ticket detail response.

        Edge cases:
            Cache fallback is used only when Fresh detail fails.
        """
        logger.info("Getting ticket %s from Freshservice", ticket_id)
        now = datetime.now(timezone.utc)
        try:
            ticket, source = await self._fresh_client.get_ticket(ticket_id)
            await self._ticket_cache_repository.upsert_ticket(ticket, source)
            return TicketDetailResponse(ticket=self._enrich_ticket(ticket, now), source=source)
        except ExternalServiceError as error:
            logger.error("Fresh get ticket failed: %s", error)
            cached = await self._ticket_cache_repository.find_by_fresh_ticket_id(ticket_id)
            if cached:
                ticket = self._ticket_from_cache(cached)
                return TicketDetailResponse(ticket=self._enrich_ticket(ticket, now), source="cache")
            ticket = mock_ticket(ticket_id)
            return TicketDetailResponse(ticket=self._enrich_ticket(ticket, now), source="mock")

    async def get_conversations(self, ticket_id: str) -> TicketConversationsResponse:
        """Fetch conversation thread for a ticket from Fresh or mock.

        Parameters:
            ticket_id: Fresh ticket identifier.

        Returns:
            Ticket conversations response.

        Edge cases:
            When Fresh fails, returns an empty item list with error=True.
        """
        logger.info("Getting conversations for ticket %s", ticket_id)
        conversations, source, error = await self._fresh_client.get_conversations(ticket_id)
        return TicketConversationsResponse(items=conversations, source=source, error=error)

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
