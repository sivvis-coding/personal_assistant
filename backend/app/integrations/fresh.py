import logging
from typing import Any, Literal

import httpx

from app.core.config import Settings
from app.core.errors import ExternalServiceError
from app.schemas.ticket import Ticket, TicketRequester

logger = logging.getLogger(__name__)


TicketListScope = Literal["mine", "all"]

# Freshservice status ID to human-readable label.
FRESH_STATUS_LABELS: dict[int | str, str] = {
    2: "open",
    3: "pending",
    4: "resolved",
    5: "closed",
    6: "waiting on customer",
    7: "waiting on third party",
}

# Freshservice priority ID to human-readable label.
FRESH_PRIORITY_LABELS: dict[int | str, str] = {
    1: "low",
    2: "medium",
    3: "high",
    4: "urgent",
}


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
        url=None,
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
                if scope == "mine" and self._settings.has_fresh_assigned_agent_id:
                    tickets = await self._list_assigned_tickets(client)
                else:
                    tickets = await self._list_all_tickets(client)
                logger.info("Fresh list tickets returned %d items", len(tickets))
                return tickets, "fresh"
        except httpx.HTTPStatusError as error:
            body = error.response.text
            logger.error("Fresh list tickets failed: %s - body: %s", error, body)
            raise ExternalServiceError(f"Fresh list tickets failed: {error} - {body}") from error
        except httpx.HTTPError as error:
            logger.error("Fresh list tickets failed: %s", error)
            raise ExternalServiceError(f"Fresh list tickets failed: {error}") from error

    async def _list_assigned_tickets(self, client: httpx.AsyncClient) -> list[Ticket]:
        """List tickets assigned to the configured agent.

        Freshservice's filter endpoint accepts `agent_id` for assigned agents,
        while direct list endpoints use `responder_id`. The client tries
        `agent_id` first, then the configured field, then falls back to fetching
        all tickets and filtering locally.
        """
        agent_id = self._settings.fresh_assigned_agent_id.strip()
        configured_field = self._settings.fresh_assigned_agent_field.strip() or "agent_id"
        fields_to_try = ["agent_id"]
        if configured_field != "agent_id":
            fields_to_try.append(configured_field)

        for field in fields_to_try:
            try:
                tickets = await self._list_with_filter(client, field, agent_id)
                logger.info("Assigned tickets loaded using filter field '%s'", field)
                return tickets
            except httpx.HTTPStatusError as error:
                if error.response.status_code == 400:
                    logger.warning("Filter field '%s' rejected: %s", field, error.response.text)
                    continue
                raise

        logger.info("Falling back to local responder_id filtering")
        all_tickets = await self._list_all_tickets(client)
        return [ticket for ticket in all_tickets if str(ticket.raw.get("responder_id")) == agent_id]

    def _fresh_params(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        """Build query parameters including workspace when configured.

        Parameters:
            extra: Additional parameters to merge.

        Returns:
            Query parameters for Freshservice requests.
        """
        params: dict[str, Any] = dict(extra) if extra else {}
        if self._settings.fresh_workspace_id.strip():
            params["workspace_id"] = self._settings.fresh_workspace_id.strip()
        return params

    async def _list_with_filter(
        self, client: httpx.AsyncClient, field: str, value: str
    ) -> list[Ticket]:
        """List tickets using the Freshservice filter endpoint.

        Note:
            The filter endpoint does not accept the `include` parameter, so
            requester details are not populated for these results.
        """
        url = f"{self._settings.fresh_base_url.rstrip('/')}/api/v2/tickets/filter"
        params = self._fresh_params({"query": f'"{field}:{value}"'})
        logger.info("Fresh filter request: %s params=%s", url, params)
        response = await client.get(url, auth=(self._settings.fresh_api_key, "X"), params=params)
        response.raise_for_status()
        return [self._normalize_ticket(item) for item in self._extract_ticket_list(response.json())]

    async def _list_all_tickets(self, client: httpx.AsyncClient) -> list[Ticket]:
        """List all tickets without server-side filtering."""
        url = f"{self._settings.fresh_base_url.rstrip('/')}/api/v2/tickets"
        params = self._fresh_params({"include": "requester"})
        logger.info("Fresh list all request: %s params=%s", url, params)
        response = await client.get(
            url, auth=(self._settings.fresh_api_key, "X"), params=params
        )
        response.raise_for_status()
        return [self._normalize_ticket(item) for item in self._extract_ticket_list(response.json())]

    def _build_ticket_list_request(self, scope: TicketListScope) -> tuple[str, dict[str, str]]:
        """Build a representative Fresh ticket list request for debugging.

        Parameters:
            scope: Ticket visibility scope requested by the caller.

        Returns:
            Tuple with API path and query parameters.

        Edge cases:
            The mine scope requires an explicit Fresh agent ID; without it the client falls back to all tickets.
        """
        if scope == "mine" and self._settings.has_fresh_assigned_agent_id:
            assigned_field = self._settings.fresh_assigned_agent_field.strip() or "responder_id"
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
                url = f"{self._settings.fresh_base_url.rstrip('/')}/api/v2/tickets/{ticket_id}"
                params = self._fresh_params({"include": "requester"})
                logger.info("Fresh get ticket request: %s params=%s", url, params)
                response = await client.get(
                    url,
                    auth=(self._settings.fresh_api_key, "X"),
                    params=params,
                )
                response.raise_for_status()
                return self._normalize_ticket(response.json()), "fresh"
        except httpx.HTTPStatusError as error:
            body = error.response.text
            logger.error("Fresh get ticket failed: %s - body: %s", error, body)
            raise ExternalServiceError(f"Fresh get ticket failed: {error} - {body}") from error
        except httpx.HTTPError as error:
            logger.error("Fresh get ticket failed: %s", error)
            raise ExternalServiceError(f"Fresh get ticket failed: {error}") from error

    async def add_note(self, ticket_id: str, body: str, *, private: bool = True) -> dict[str, Any]:
        """Add a note (conversation entry) to a Fresh ticket.

        Parameters:
            ticket_id: Fresh ticket identifier.
            body: Note body.
            private: When True the note is a private agent note not visible to the
                requester.  Defaults to True to prevent accidental customer exposure.

        Returns:
            Fresh API response payload.

        Edge cases:
            Mock mode returns a deterministic payload without hitting the API.
            Use add_reply for customer-visible responses (requires HITL approval).
        """
        if not self._settings.has_fresh_credentials:
            return {"mock": True, "ticket_id": str(ticket_id), "body": body, "private": private}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"{self._settings.fresh_base_url.rstrip('/')}/api/v2/tickets/{ticket_id}/notes",
                    auth=(self._settings.fresh_api_key, "X"),
                    json={"body": body, "private": private},
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as error:
            raise ExternalServiceError(f"Fresh add note failed: {error}") from error

    async def add_reply(self, ticket_id: str, body: str) -> dict[str, Any]:
        """Add a public reply to a Fresh ticket (customer-visible).

        Parameters:
            ticket_id: Fresh ticket identifier.
            body: Reply body.

        Returns:
            Fresh API response payload.

        Edge cases:
            IMPORTANT: This method sends a PUBLIC reply to the customer.
            It MUST only be called after an AssistantAction has been approved
            through the HITL approval flow.  No automated workflow may call
            this method directly — use add_note for internal status updates.
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
            Numeric Fresh statuses/priorities are mapped to human-readable labels.
            Requester can arrive as a nested object or flat name/email fields.
        """
        requester = self._extract_requester(payload)
        ticket_id = str(payload.get("id"))
        return Ticket(
            id=ticket_id,
            subject=str(payload.get("subject") or "Untitled ticket"),
            status=self._normalize_status(payload.get("status")),
            priority=self._normalize_priority(payload.get("priority")),
            requester=requester,
            description=payload.get("description_text") or payload.get("description"),
            url=self._ticket_url(ticket_id),
            raw=payload,
        )

    def _ticket_url(self, ticket_id: str) -> str | None:
        """Build a direct Freshservice ticket URL when credentials are configured.

        Parameters:
            ticket_id: Fresh ticket identifier.

        Returns:
            Ticket URL or None when credentials are missing.

        Edge cases:
            Mock mode returns None because there is no real Freshservice instance.
        """
        if not self._settings.has_fresh_credentials:
            return None
        base_url = self._settings.fresh_base_url.rstrip('/')
        return f"{base_url}/a/tickets/{ticket_id}"

    @staticmethod
    def _extract_requester(payload: dict[str, Any]) -> TicketRequester:
        """Extract requester name and email from various Fresh payload shapes.

        Parameters:
            payload: Raw Fresh API ticket payload.

        Returns:
            Normalized requester.

        Edge cases:
            Freshservice list endpoint may omit requester details entirely.
        """
        requester_payload = payload.get("requester")
        if isinstance(requester_payload, dict):
            return TicketRequester(
                name=str(requester_payload.get("name") or requester_payload.get("first_name") or "Unknown requester"),
                email=requester_payload.get("email") or requester_payload.get("primary_email"),
            )

        name = payload.get("requester_name") or payload.get("name")
        email = payload.get("requester_email") or payload.get("email")
        return TicketRequester(
            name=str(name) if name else "Unknown requester",
            email=email,
        )

    @staticmethod
    def _normalize_status(value: Any) -> str:
        """Map Freshservice status ID or string to a readable label."""
        if value is None:
            return "unknown"
        return FRESH_STATUS_LABELS.get(value, str(value).lower())

    @staticmethod
    def _normalize_priority(value: Any) -> str:
        """Map Freshservice priority ID or string to a readable label."""
        if value is None:
            return "unknown"
        return FRESH_PRIORITY_LABELS.get(value, str(value).lower())
