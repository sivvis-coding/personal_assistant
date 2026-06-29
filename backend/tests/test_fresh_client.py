import pytest

from app.core.config import Settings
from app.core.errors import ExternalServiceError
from app.integrations.fresh import FreshClient


def test_should_extract_tickets_when_freshservice_returns_wrapped_list() -> None:
    """Verify Freshservice list responses are unwrapped correctly.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Freshservice wraps ticket lists in a top-level tickets property.
    """
    # Arrange
    client = FreshClient(Settings())
    payload = {"tickets": [{"id": 123, "subject": "VPN access"}]}

    # Act
    tickets = client._extract_ticket_list(payload)

    # Assert
    assert tickets == [{"id": 123, "subject": "VPN access"}]


def test_should_build_assigned_ticket_filter_request_when_agent_id_is_configured() -> None:
    """Verify assigned-ticket scope uses Freshservice filter endpoint.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Freshservice requires an explicit agent ID because the backend cannot infer the current user.
    """
    # Arrange
    client = FreshClient(Settings(fresh_assigned_agent_id="123456"))

    # Act
    path, params = client._build_ticket_list_request("mine")

    # Assert
    assert path == "/api/v2/tickets/filter"
    assert params == {"query": '"agent_id:123456"'}


def test_should_build_assigned_ticket_filter_request_with_configured_field() -> None:
    """Verify assigned-ticket filter field can be configured per Fresh account.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Fresh accounts can expose assignment fields differently across products or API filters.
    """
    # Arrange
    client = FreshClient(Settings(fresh_assigned_agent_id="123456", fresh_assigned_agent_field="responder_id"))

    # Act
    path, params = client._build_ticket_list_request("mine")

    # Assert
    assert path == "/api/v2/tickets/filter"
    assert params == {"query": '"responder_id:123456"'}


def test_should_build_all_ticket_request_when_scope_is_all() -> None:
    """Verify all-ticket scope uses the regular list endpoint.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Configured agent ID must not affect explicit all-ticket requests.
    """
    # Arrange
    client = FreshClient(Settings(fresh_assigned_agent_id="123456"))

    # Act
    path, params = client._build_ticket_list_request("all")

    # Assert
    assert path == "/api/v2/tickets"
    assert params == {}


def test_should_fallback_to_all_ticket_request_when_agent_id_is_missing() -> None:
    """Verify assigned-ticket scope does not invent an agent identity.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Missing agent ID falls back to regular list endpoint instead of guessing.
    """
    # Arrange
    client = FreshClient(Settings())

    # Act
    path, params = client._build_ticket_list_request("mine")

    # Assert
    assert path == "/api/v2/tickets"
    assert params == {}


def test_should_extract_tickets_when_freshdesk_returns_bare_list() -> None:
    """Verify Freshdesk-style list responses remain supported.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Bare list support keeps Freshdesk compatibility.
    """
    # Arrange
    client = FreshClient(Settings())
    payload = [{"id": 123, "subject": "VPN access"}]

    # Act
    tickets = client._extract_ticket_list(payload)

    # Assert
    assert tickets == payload


def test_should_raise_error_when_ticket_list_items_are_not_objects() -> None:
    """Verify invalid ticket list items fail with integration error.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Dict iteration bugs can otherwise pass strings into ticket normalization.
    """
    # Arrange
    client = FreshClient(Settings())
    payload = {"tickets": ["invalid-ticket"]}

    # Act / Assert
    with pytest.raises(ExternalServiceError, match="ticket items must be objects"):
        client._extract_ticket_list(payload)


def test_should_extract_ticket_when_freshservice_returns_wrapped_detail() -> None:
    """Verify Freshservice detail responses are unwrapped correctly.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Freshservice wraps ticket detail in a top-level ticket property.
    """
    # Arrange
    client = FreshClient(Settings())
    payload = {"ticket": {"id": 123, "subject": "VPN access"}}

    # Act
    ticket = client._extract_ticket_detail(payload)

    # Assert
    assert ticket == {"id": 123, "subject": "VPN access"}


def test_should_normalize_ticket_after_extracting_freshservice_payload() -> None:
    """Verify Freshservice payloads normalize into internal tickets.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Numeric status and priority values are preserved as display-safe strings.
    """
    # Arrange
    client = FreshClient(Settings())
    payload = {
        "ticket": {
            "id": 123,
            "subject": "VPN access",
            "status": 2,
            "priority": 3,
            "requester_name": "Ada Lovelace",
            "requester_email": "ada@example.com",
            "description_text": "Cannot connect to VPN.",
        }
    }

    # Act
    ticket = client._normalize_ticket(client._extract_ticket_detail(payload))

    # Assert
    assert ticket.id == "123"
    assert ticket.subject == "VPN access"
    assert ticket.status == "2"
    assert ticket.priority == "3"
    assert ticket.requester.name == "Ada Lovelace"
    assert ticket.requester.email == "ada@example.com"
    assert ticket.description == "Cannot connect to VPN."
