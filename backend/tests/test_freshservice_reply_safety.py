"""Safety tests for the Freshservice public-reply protection.

The app contract is: automated workflows MUST NEVER send a public reply to a
customer without explicit human approval via an AssistantAction (HITL flow).

These tests enforce that contract at multiple levels:

  1. Static source analysis — update_ticket (automated note path) must not call
     add_reply.  reply_ticket (public reply path) must only be reachable via the
     executor after an approved AssistantAction.

  2. Behavioral adapter — update_ticket routes to add_note (private), not
     add_reply.  reply_ticket routes to add_reply and returns the API response.

  3. Behavioral executor — AssistantActionExecutor._reply_freshservice_ticket
     calls the adapter and stores the result; safety policy blocks blank bodies
     and missing ticket_id before execution reaches the adapter.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.assistant.safety_policy import AssistantSafetyPolicy
from app.assistant.schemas.actions import AssistantAction
from app.tools.freshservice.adapter import FreshserviceAdapter
from app.tools.freshservice.schemas import ReplyTicketInput, UpdateTicketInput

ADAPTER_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "tools"
    / "freshservice"
    / "adapter.py"
)

EXECUTOR_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "assistant"
    / "action_executor.py"
)


# ---------------------------------------------------------------------------
# Static source-analysis tests
# ---------------------------------------------------------------------------


def test_update_ticket_must_not_call_add_reply() -> None:
    """Verify update_ticket source never calls add_reply directly.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        This test guards against regression: update_ticket previously called
        add_reply which would have sent an unapproved public customer reply
        the moment the event bus gained a subscriber.
    """
    source = ADAPTER_SOURCE.read_text(encoding="utf-8")
    # Extract only the update_ticket method body
    update_ticket_body = source.split("async def update_ticket", maxsplit=1)[1].split(
        "async def reply_ticket", maxsplit=1
    )[0]

    # Check for the actual call-site expression (with opening paren) so that docstrings
    # or comments that mention add_reply by name do not cause a false positive.
    assert "add_reply(" not in update_ticket_body


def test_reply_ticket_calls_client_add_reply() -> None:
    """Verify reply_ticket source calls self._client.add_reply (behind HITL gate).

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        reply_ticket is the adapter-level public reply path.  It is intentionally
        a live call because it is only reachable via AssistantActionExecutor after
        an approved reply_freshservice_ticket action passes safety policy.
        This test breaks if someone accidentally re-introduces the no-op.
    """
    source = ADAPTER_SOURCE.read_text(encoding="utf-8")
    reply_ticket_body = source.split("async def reply_ticket", maxsplit=1)[1].split(
        "async def search_tickets", maxsplit=1
    )[0]

    assert "self._client.add_reply(" in reply_ticket_body


# ---------------------------------------------------------------------------
# Behavioral adapter tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_ticket_calls_add_note_not_add_reply() -> None:
    """update_ticket must route note updates to add_note (private note).

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Internal link notifications must never be visible to the customer
        without explicit approval.
    """
    # Arrange
    mock_client = MagicMock()
    mock_client.add_note = AsyncMock(return_value={"id": "note-1", "private": True})
    mock_client.add_reply = AsyncMock()

    adapter = FreshserviceAdapter(ticket_service=MagicMock(), client=mock_client)
    input_data = UpdateTicketInput(
        ticket_id="42",
        changes={"note": "ClickUp task created: https://app.clickup.com/t/abc"},
    )

    # Act
    result = await adapter.update_ticket(input_data)

    # Assert: add_note was called with private=True
    mock_client.add_note.assert_awaited_once_with(
        "42",
        "ClickUp task created: https://app.clickup.com/t/abc",
        private=True,
    )
    # Assert: add_reply was never called
    mock_client.add_reply.assert_not_awaited()
    assert result == {"id": "note-1", "private": True}


@pytest.mark.asyncio
async def test_update_ticket_without_note_returns_mock_payload() -> None:
    """update_ticket with no note key must return a mock payload without any API call.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Callers may pass empty changes dicts; the adapter must not crash or call
        any write API in that case.
    """
    mock_client = MagicMock()
    mock_client.add_note = AsyncMock()
    mock_client.add_reply = AsyncMock()

    adapter = FreshserviceAdapter(ticket_service=MagicMock(), client=mock_client)
    input_data = UpdateTicketInput(ticket_id="42", changes={"status": "pending"})

    result = await adapter.update_ticket(input_data)

    mock_client.add_note.assert_not_awaited()
    mock_client.add_reply.assert_not_awaited()
    assert result == {"mock": True, "ticket_id": "42", "changes": {"status": "pending"}}


@pytest.mark.asyncio
async def test_reply_ticket_calls_add_reply_and_returns_response() -> None:
    """reply_ticket must delegate to add_reply and return the API response.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        This path is only reachable via AssistantActionExecutor, which validates
        the action through AssistantSafetyPolicy before calling the adapter.
    """
    mock_client = MagicMock()
    mock_client.add_reply = AsyncMock(return_value={"id": "reply-1", "ticket_id": "42"})

    adapter = FreshserviceAdapter(ticket_service=MagicMock(), client=mock_client)
    input_data = ReplyTicketInput(ticket_id="42", body="Your ticket has been resolved.")

    result = await adapter.reply_ticket(input_data)

    mock_client.add_reply.assert_awaited_once_with("42", "Your ticket has been resolved.")
    assert result == {"id": "reply-1", "ticket_id": "42"}


# ---------------------------------------------------------------------------
# Safety policy tests
# ---------------------------------------------------------------------------


def _make_proposed_action(**overrides) -> AssistantAction:
    """Build a minimal proposed reply_freshservice_ticket AssistantAction."""
    defaults = {
        "id": "action-1",
        "action_type": "reply_freshservice_ticket",
        "status": "proposed",
        "title": "Reply to ticket",
        "description": "Send a public reply",
        "ticket_id": "42",
        "payload": {"body": "Hello, your issue has been resolved."},
        "requires_approval": True,
    }
    defaults.update(overrides)
    return AssistantAction(**defaults)


def test_safety_policy_accepts_valid_reply_action() -> None:
    """Safety policy must not raise for a well-formed reply action.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        All required fields present and status is proposed.
    """
    policy = AssistantSafetyPolicy()
    action = _make_proposed_action()
    policy.ensure_can_execute(action)  # must not raise


def test_safety_policy_rejects_reply_action_without_ticket_id() -> None:
    """Safety policy must reject a reply action missing a ticket_id.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Without ticket_id the executor cannot determine which ticket to reply to.
    """
    policy = AssistantSafetyPolicy()
    action = _make_proposed_action(ticket_id=None)
    with pytest.raises(ValueError, match="ticket_id"):
        policy.ensure_can_execute(action)


def test_safety_policy_rejects_reply_action_with_empty_body() -> None:
    """Safety policy must reject a reply action with an empty body.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Blank replies must never reach the customer even if the action is proposed.
    """
    policy = AssistantSafetyPolicy()
    action = _make_proposed_action(payload={"body": "   "})
    with pytest.raises(ValueError, match="body"):
        policy.ensure_can_execute(action)


def test_safety_policy_rejects_reply_action_with_missing_body_key() -> None:
    """Safety policy must reject a reply action payload with no 'body' key.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Malformed payloads must not silently send a None or empty reply.
    """
    policy = AssistantSafetyPolicy()
    action = _make_proposed_action(payload={})
    with pytest.raises(ValueError, match="body"):
        policy.ensure_can_execute(action)


# ---------------------------------------------------------------------------
# Behavioral executor tests
# ---------------------------------------------------------------------------


def _make_executor(freshservice_adapter: FreshserviceAdapter):
    """Build an AssistantActionExecutor with fake dependencies."""
    from app.assistant.action_executor import AssistantActionExecutor

    return AssistantActionExecutor(
        action_repository=MagicMock(),
        safety_policy=AssistantSafetyPolicy(),
        ticket_to_clickup_tool=MagicMock(),
        clickup_time_tool=MagicMock(),
        freshservice_adapter=freshservice_adapter,
    )


@pytest.mark.asyncio
async def test_executor_reply_action_calls_adapter_and_stores_result() -> None:
    """Executor must call reply_ticket on the adapter and mark the action completed.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        The executor stores the Fresh API response in the action result.
    """
    # Arrange
    mock_client = MagicMock()
    mock_client.add_reply = AsyncMock(return_value={"id": "reply-1"})
    adapter = FreshserviceAdapter(ticket_service=MagicMock(), client=mock_client)

    completed_action = _make_proposed_action(status="completed")
    mock_repo = MagicMock()
    mock_repo.get_action = AsyncMock(return_value=_make_proposed_action())
    mock_repo.update_status = AsyncMock(return_value=completed_action)

    from app.assistant.action_executor import AssistantActionExecutor

    executor = AssistantActionExecutor(
        action_repository=mock_repo,
        safety_policy=AssistantSafetyPolicy(),
        ticket_to_clickup_tool=MagicMock(),
        clickup_time_tool=MagicMock(),
        freshservice_adapter=adapter,
    )

    # Act
    result = await executor.approve("action-1")

    # Assert: adapter called add_reply with correct args
    mock_client.add_reply.assert_awaited_once_with(
        "42", "Hello, your issue has been resolved."
    )
    # Assert: repository updated to completed with the API response
    mock_repo.update_status.assert_awaited_once_with(
        "action-1", "completed", result={"response": {"id": "reply-1"}}
    )
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_executor_reply_action_stores_failed_status_on_adapter_error() -> None:
    """Executor must catch adapter exceptions and persist a failed action.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Fresh API errors must not propagate as unhandled exceptions.
    """
    from app.core.errors import ExternalServiceError

    mock_client = MagicMock()
    mock_client.add_reply = AsyncMock(side_effect=ExternalServiceError("Connection timeout"))
    adapter = FreshserviceAdapter(ticket_service=MagicMock(), client=mock_client)

    failed_action = _make_proposed_action(status="failed")
    mock_repo = MagicMock()
    mock_repo.get_action = AsyncMock(return_value=_make_proposed_action())
    mock_repo.update_status = AsyncMock(return_value=failed_action)

    from app.assistant.action_executor import AssistantActionExecutor

    executor = AssistantActionExecutor(
        action_repository=mock_repo,
        safety_policy=AssistantSafetyPolicy(),
        ticket_to_clickup_tool=MagicMock(),
        clickup_time_tool=MagicMock(),
        freshservice_adapter=adapter,
    )

    result = await executor.approve("action-1")

    mock_repo.update_status.assert_awaited_once_with(
        "action-1", "failed", result={"message": "Connection timeout", "error": True}
    )
    assert result.status == "failed"
