"""Bulk history-harvesting client for Freshservice (Insights archive).

Deliberately separate from FreshClient so the live ticket UI path is untouched.
It adds what bulk ingestion needs and the live client lacks: real pagination,
shared rate limiting, and 429 backoff. Normalization is reused from FreshClient
rather than duplicated.
"""

import logging
from datetime import datetime, timezone

import httpx

from app.core.time import utc_now
from app.integrations.fresh import (
    FreshClient,
    mock_ticket,
)
from app.integrations.rate_limiter import AsyncRateLimiter, request_with_retry

logger = logging.getLogger(__name__)

# Freshservice list endpoint caps at 100 items per page.
PER_PAGE = 100


class FreshArchiveClient:
    """Fetch a workspace's full ticket history, page by page, rate-limited.

    Parameters:
        base_url: Freshservice base URL for this workspace.
        api_key: Freshservice API key.
        workspace_id: Numeric workspace ID (sent as a query param).
        rate_limiter: Shared limiter pacing every request.
        semaphore: Shared semaphore bounding conversation-fetch concurrency.
        timeout: Per-request timeout in seconds.

    Returns:
        Client yielding normalized archive-ready ticket/conversation dicts.

    Edge cases:
        With no base_url/api_key it operates in mock mode so local dev renders
        without secrets, mirroring FreshClient's credential-gated behavior.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        workspace_id: str,
        rate_limiter: AsyncRateLimiter,
        semaphore: "object | None" = None,
        timeout: int = 30,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._workspace_id = workspace_id
        self._rate_limiter = rate_limiter
        self._semaphore = semaphore
        self._timeout = timeout

    @property
    def has_credentials(self) -> bool:
        """Return whether this workspace has live Freshservice credentials."""
        return bool(self._base_url and self._api_key)

    async def fetch_tickets_page(self, updated_since: datetime, page: int) -> list[dict]:
        """Fetch one page of tickets updated since a cursor, oldest first.

        Parameters:
            updated_since: Only tickets updated at/after this time.
            page: 1-based page number.

        Returns:
            Archive-ready ticket dicts (without conversations). Empty list ends
            the page loop; a full page (PER_PAGE) signals more may follow.

        Edge cases:
            Mock mode returns two deterministic tickets on page 1 only.
        """
        if not self.has_credentials:
            return self._mock_ticket_docs() if page == 1 else []

        params = {
            "workspace_id": self._workspace_id,
            # Freshservice requires a whole-second ISO8601 timestamp with a "Z"
            # suffix; microseconds or a "+00:00" offset are rejected with a 400.
            "updated_since": _fresh_ts(updated_since),
            "per_page": PER_PAGE,
            "page": page,
            "order_by": "updated_at",
            "order_type": "asc",
            # "description" is NOT a valid include on the list endpoint; only
            # requester/stats/tags/... are. Ticket bodies come from conversations.
            "include": "requester,stats",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await request_with_retry(
                client,
                "GET",
                f"{self._base_url}/api/v2/tickets",
                rate_limiter=self._rate_limiter,
                auth=(self._api_key, "X"),
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
        raw_items = payload.get("tickets", payload) if isinstance(payload, dict) else payload
        if not isinstance(raw_items, list):
            return []
        return [self._build_archive_doc(item) for item in raw_items if isinstance(item, dict)]

    async def fetch_conversations(self, ticket_id: str) -> list[dict]:
        """Fetch all conversation entries for a ticket, paginated.

        Parameters:
            ticket_id: Freshservice ticket identifier.

        Returns:
            Normalized conversation dicts (reusing FreshClient normalization).

        Edge cases:
            Mock mode returns deterministic conversations. Per-ticket failures
            propagate to the caller, which decides whether to skip.
        """
        if not self.has_credentials:
            return [c.model_dump(mode="json") for c in FreshClient.mock_conversations(str(ticket_id))]

        conversations: list[dict] = []
        page = 1
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            while True:
                response = await request_with_retry(
                    client,
                    "GET",
                    f"{self._base_url}/api/v2/tickets/{ticket_id}/conversations",
                    rate_limiter=self._rate_limiter,
                    auth=(self._api_key, "X"),
                    params={"per_page": PER_PAGE, "page": page},
                )
                response.raise_for_status()
                payload = response.json()
                items = payload if isinstance(payload, list) else payload.get("conversations", [])
                if not items:
                    break
                conversations.extend(
                    FreshClient._normalize_conversation(item).model_dump(mode="json")
                    for item in items
                    if isinstance(item, dict)
                )
                if len(items) < PER_PAGE:
                    break
                page += 1
        return conversations

    def _build_archive_doc(self, raw: dict) -> dict:
        """Build an archive-ready ticket dict from a raw Freshservice payload.

        Reuses FreshClient's status/priority/requester normalization; stores the
        full raw payload for later reprocessing. Conversations are attached by
        the service, not here.
        """
        stats = raw.get("stats") or {}
        return {
            "workspace_id": self._workspace_id,
            "ticket_id": str(raw.get("id")),
            "subject": str(raw.get("subject") or "Untitled ticket"),
            "status": FreshClient._normalize_status(raw.get("status")),
            "priority": FreshClient._normalize_priority(raw.get("priority")),
            "requester": FreshClient._extract_requester(raw).model_dump(),
            "description": raw.get("description_text") or FreshClient._strip_html(raw.get("description") or ""),
            "custom_fields": dict(raw.get("custom_fields") or {}),
            "created_at_fresh": _parse_dt(raw.get("created_at")),
            "updated_at_fresh": _parse_dt(raw.get("updated_at")),
            "resolved_at": _parse_dt(stats.get("resolved_at")),
            "tags": list(raw.get("tags") or []),
            "raw": raw,
        }

    def _mock_ticket_docs(self) -> list[dict]:
        """Return deterministic archive docs for mock mode."""
        docs = []
        for tid in ("9001", "9002"):
            t = mock_ticket(tid)
            docs.append(
                {
                    "workspace_id": self._workspace_id,
                    "ticket_id": tid,
                    "subject": t.subject,
                    "status": "resolved",
                    "priority": t.priority,
                    "requester": t.requester.model_dump(),
                    "description": t.description,
                    "custom_fields": {},
                    "created_at_fresh": utc_now(),
                    "updated_at_fresh": utc_now(),
                    "resolved_at": utc_now(),
                    "tags": ["mock"],
                    "raw": t.raw,
                }
            )
        return docs


def _fresh_ts(dt: datetime) -> str:
    """Format a datetime as Freshservice's expected whole-second ISO8601 + 'Z'."""
    aware = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_dt(value: object) -> datetime | None:
    """Parse a Freshservice ISO-8601 timestamp into a datetime, or None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
