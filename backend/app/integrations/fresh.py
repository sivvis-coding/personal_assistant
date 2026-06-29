from typing import Any, Literal

import httpx

from app.core.config import Settings
from app.core.errors import ExternalServiceError
from app.schemas.ticket import Ticket, TicketRequester


TicketListScope = Literal["mine", "all"]


def mock_ticket(ticket_id: str = "1001") -> Ticket:
    """Create a deterministic mock ticket.

    Parameters:
        ticket_id: Ticket ID to place in the mock payload.

    Returns:
        Normalized mock ticket.

    Edge cases:
        Used when Fresh credentials are missing or cache has no data.
    """
    return Ticket(
        id=str(ticket_id),
        subject="Cannot access reporting dashboard",
        status="open",
        priority="high",
        requester=TicketRequester(name="Mock Customer", email="customer@example.com"),
        description="The customer cannot access the reporting dashboard after the latest release.",
        raw={"id": str(ticket_id), "mock": True},
    )


class FreshClient:
    """Client for Freshdesk/Freshservice ticket operations.

    Parameters:
        settings: Application settings with Fresh credentials.

    Returns:
        Fresh integration client.

    Edge cases:
        Missing credentials switch read operations to mock mode.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def list_tickets(self, scope: TicketListScope = "mine") -> tuple[list[Ticket], str]:
        """List Fresh tickets or return mock tickets.

        Parameters:
            scope: Ticket visibility scope. mine filters by configured assigned agent ID.

        Returns:
            Tuple of tickets and source label.

        Edge cases:
            Fresh API failures raise ExternalServiceError so callers can fallback.
        """
        if not self._settings.has_fresh_credentials:
            return [mock_ticket("1001"), mock_ticket("1002")], "mock"
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                path, params = self._build_ticket_list_request(scope)
                response = await client.get(
                    f"{self._settings.fresh_base_url.rstrip('/')}{path}",
                    auth=(self._settings.fresh_api_key, "X"),
                    params=params,
                )
                response.raise_for_status()
                ticket_payloads = self._extract_ticket_list(response.json())
                return [self._normalize_ticket(item) for item in ticket_payloads], "fresh"
        except httpx.HTTPError as error:
            raise ExternalServiceError(f"Fresh list tickets failed: {error}") from error

    def _build_ticket_list_request(self, scope: TicketListScope) -> tuple[str, dict[str, str]]:
        """Build Fresh ticket list path and query parameters.

        Parameters:
            scope: Ticket visibility scope requested by the caller.

        Returns:
            Tuple with API path and query parameters.

        Edge cases:
            The mine scope requires an explicit Fresh agent ID; without it the client falls back to all tickets.
        """
        if scope == "mine" and self._settings.has_fresh_assigned_agent_id:
            assigned_field = self._settings.fresh_assigned_agent_field.strip() or "agent_id"
            assigned_agent_id = self._settings.fresh_assigned_agent_id.strip()
            return "/api/v2/tickets/filter", {"query": f'"{assigned_field}:{assigned_agent_id}"'}

        return "/api/v2/tickets", {}

    async def get_ticket(self, ticket_id: str) -> tuple[Ticket, str]:
        """Get a Fresh ticket by ID or return a mock ticket.

        Parameters:
            ticket_id: Fresh ticket identifier.

        Returns:
            Tuple of ticket and source label.

        Edge cases:
            Fresh API failures raise ExternalServiceError so cache fallback can run.
        """
        if not self._settings.has_fresh_credentials:
            return mock_ticket(ticket_id), "mock"
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"{self._settings.fresh_base_url.rstrip('/')}/api/v2/tickets/{ticket_id}",
                    auth=(self._settings.fresh_api_key, "X"),
                )
                response.raise_for_status()
                ticket_payload = self._extract_ticket_detail(response.json())
                return self._normalize_ticket(ticket_payload), "fresh"
        except httpx.HTTPError as error:
            raise ExternalServiceError(f"Fresh get ticket failed: {error}") from error

    async def add_reply(self, ticket_id: str, body: str) -> dict[str, Any]:
        """Add a reply to a Fresh ticket.

        Parameters:
            ticket_id: Fresh ticket identifier.
            body: Reply body.

        Returns:
            Fresh API response payload.

        Edge cases:
            This method is intentionally not used by workflows to avoid automatic replies.
        """
        if not self._settings.has_fresh_credentials:
            return {"mock": True, "ticket_id": str(ticket_id), "body": body}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"{self._settings.fresh_base_url.rstrip('/')}/api/v2/tickets/{ticket_id}/reply",
                    auth=(self._settings.fresh_api_key, "X"),
                    json={"body": body},
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as error:
            raise ExternalServiceError(f"Fresh add reply failed: {error}") from error

    def _extract_ticket_list(self, payload: Any) -> list[dict[str, Any]]:
        """Extract ticket dictionaries from Fresh list response payload.

        Parameters:
            payload: Raw Fresh API response payload.

        Returns:
            List of raw ticket dictionaries.

        Edge cases:
            Freshdesk can return a bare list while Freshservice returns {"tickets": [...]}.
            Non-object ticket items are rejected instead of failing with attribute errors later.
        """
        if isinstance(payload, list):
            ticket_items = payload
        elif isinstance(payload, dict) and isinstance(payload.get("tickets"), list):
            ticket_items = payload["tickets"]
        else:
            raise ExternalServiceError("Fresh list tickets failed: unexpected response shape")

        if not all(isinstance(item, dict) for item in ticket_items):
            raise ExternalServiceError("Fresh list tickets failed: ticket items must be objects")

        return ticket_items

    def _extract_ticket_detail(self, payload: Any) -> dict[str, Any]:
        """Extract ticket dictionary from Fresh detail response payload.

        Parameters:
            payload: Raw Fresh API response payload.

        Returns:
            Raw ticket dictionary.

        Edge cases:
            Freshdesk-like responses can be bare ticket objects while Freshservice wraps them in {"ticket": {...}}.
        """
        if isinstance(payload, dict) and isinstance(payload.get("ticket"), dict):
            return payload["ticket"]

        if isinstance(payload, dict):
            return payload

        raise ExternalServiceError("Fresh get ticket failed: unexpected response shape")

    def _normalize_ticket(self, payload: dict[str, Any]) -> Ticket:
        """Normalize a Fresh payload into internal ticket schema.

        Parameters:
            payload: Raw Fresh API payload.

        Returns:
            Normalized ticket.

        Edge cases:
            Numeric Fresh statuses/priorities are converted to strings for display stability.
        """
        requester = TicketRequester(
            name=str(payload.get("requester_name") or payload.get("name") or "Unknown requester"),
            email=payload.get("requester_email") or payload.get("email"),
        )
        return Ticket(
            id=str(payload.get("id")),
            subject=str(payload.get("subject") or "Untitled ticket"),
            status=str(payload.get("status") or "unknown"),
            priority=str(payload.get("priority") or "unknown"),
            requester=requester,
            description=payload.get("description_text") or payload.get("description"),
            raw=payload,
        )
