"""Tests for FreshClient conversation methods and the conversations API endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.integrations.fresh import FreshClient
from app.schemas.ticket import TicketConversation, TicketConversationsResponse
from app.services.ticket_service import TicketService


# ---------------------------------------------------------------------------
# FreshClient._normalize_conversation — kind mapping
# ---------------------------------------------------------------------------


def test_normalize_conversation_maps_private_to_private_note() -> None:
    """private=True always produces kind='private_note'."""
    payload = {"id": "1", "private": True, "incoming": False, "body_text": "Internal note"}
    result = FreshClient._normalize_conversation(payload)
    assert result.kind == "private_note"
    assert result.private is True


def test_normalize_conversation_maps_incoming_to_customer_reply() -> None:
    """private=False and incoming=True produces kind='customer_reply'."""
    payload = {"id": "2", "private": False, "incoming": True, "body_text": "Hello"}
    result = FreshClient._normalize_conversation(payload)
    assert result.kind == "customer_reply"
    assert result.incoming is True


def test_normalize_conversation_maps_outgoing_to_agent_reply() -> None:
    """private=False and incoming=False produces kind='agent_reply'."""
    payload = {"id": "3", "private": False, "incoming": False, "body_text": "Thank you"}
    result = FreshClient._normalize_conversation(payload)
    assert result.kind == "agent_reply"


def test_normalize_conversation_prefers_body_text_over_html() -> None:
    """body_text is returned when both body_text and body are present."""
    payload = {
        "id": "4",
        "private": False,
        "incoming": False,
        "body_text": "Plain text",
        "body": "<p>HTML body</p>",
    }
    result = FreshClient._normalize_conversation(payload)
    assert result.body_text == "Plain text"


def test_normalize_conversation_falls_back_to_stripped_html_when_no_body_text() -> None:
    """body_html is stripped and used as body_text when body_text is absent."""
    payload = {
        "id": "5",
        "private": False,
        "incoming": False,
        "body": "<p>Hello <b>world</b></p>",
    }
    result = FreshClient._normalize_conversation(payload)
    assert result.body_text == "Hello world"


def test_normalize_conversation_parses_iso_created_at() -> None:
    """ISO created_at strings are parsed into datetime objects."""
    payload = {
        "id": "6",
        "private": False,
        "incoming": True,
        "created_at": "2024-03-15T10:00:00Z",
    }
    result = FreshClient._normalize_conversation(payload)
    assert result.created_at is not None
    assert result.created_at.year == 2024
    assert result.created_at.month == 3
    assert result.created_at.day == 15


def test_normalize_conversation_handles_malformed_created_at_silently() -> None:
    """Malformed created_at does not raise."""
    payload = {
        "id": "7",
        "private": False,
        "incoming": False,
        "created_at": "not-a-date",
    }
    result = FreshClient._normalize_conversation(payload)
    assert result.created_at is None


# ---------------------------------------------------------------------------
# FreshClient.mock_conversations
# ---------------------------------------------------------------------------


def test_mock_conversations_returns_three_entries() -> None:
    """mock_conversations returns exactly one entry of each kind."""
    entries = FreshClient.mock_conversations("42")
    assert len(entries) == 3
    kinds = {entry.kind for entry in entries}
    assert kinds == {"customer_reply", "agent_reply", "private_note"}


def test_mock_conversations_uses_ticket_id_in_entry_ids() -> None:
    """mock_conversations embeds ticket_id in conversation entry ids."""
    entries = FreshClient.mock_conversations("99")
    assert all("99" in entry.id for entry in entries)


# ---------------------------------------------------------------------------
# FreshClient.get_conversations — mock mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_conversations_returns_mock_when_no_credentials() -> None:
    """get_conversations returns mock conversations when credentials are absent."""
    client = FreshClient(Settings())
    conversations, source, error = await client.get_conversations("42")
    assert error is False
    assert source == "mock"
    assert len(conversations) == 3


# ---------------------------------------------------------------------------
# FreshClient.get_conversations — graceful failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_conversations_returns_empty_with_error_on_http_failure() -> None:
    """get_conversations never raises; returns empty list with error=True on HTTP failure."""
    import httpx

    settings = Settings(
        fresh_api_key="key",
        fresh_base_url="https://example.freshservice.com",
    )
    client = FreshClient(settings)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        conversations, source, error = await client.get_conversations("42")

    assert error is True
    assert conversations == []
    assert source == "fresh"


@pytest.mark.asyncio
async def test_get_conversations_returns_empty_with_error_on_http_status_error() -> None:
    """get_conversations handles HTTP 404 / 500 without propagating."""
    import httpx

    settings = Settings(
        fresh_api_key="key",
        fresh_base_url="https://example.freshservice.com",
    )
    client = FreshClient(settings)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "403 Forbidden",
                request=MagicMock(),
                response=mock_response,
            )
        )
        mock_http.get = AsyncMock(return_value=mock_response)

        conversations, source, error = await client.get_conversations("42")

    assert error is True
    assert conversations == []
    assert source == "fresh"


# ---------------------------------------------------------------------------
# TicketService.get_conversations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ticket_service_get_conversations_returns_mock_data() -> None:
    """TicketService.get_conversations returns mock conversations in mock mode."""
    fresh_client = MagicMock()
    fresh_client.get_conversations = AsyncMock(
        return_value=(FreshClient.mock_conversations("10"), "mock", False)
    )
    ticket_cache = MagicMock()
    service = TicketService(fresh_client, ticket_cache)

    response = await service.get_conversations("10")

    assert isinstance(response, TicketConversationsResponse)
    assert response.error is False
    assert response.source == "mock"
    assert len(response.items) == 3


@pytest.mark.asyncio
async def test_ticket_service_get_conversations_propagates_error_flag() -> None:
    """TicketService.get_conversations propagates error=True from Fresh failure."""
    fresh_client = MagicMock()
    fresh_client.get_conversations = AsyncMock(return_value=([], "fresh", True))
    ticket_cache = MagicMock()
    service = TicketService(fresh_client, ticket_cache)

    response = await service.get_conversations("99")

    assert isinstance(response, TicketConversationsResponse)
    assert response.error is True
    assert response.items == []
    assert response.source == "fresh"
