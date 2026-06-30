"""Tests for app.services.sla pure functions."""

from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.ticket import Ticket, TicketRequester
from app.services.sla import AT_RISK_THRESHOLD, compute_sla, is_overdue


def _build_ticket(due_by: str | None = None, **extra_raw: object) -> Ticket:
    """Build a minimal ticket with raw metadata."""
    raw: dict = {}
    if due_by is not None:
        raw["due_by"] = due_by
    raw.update(extra_raw)
    return Ticket(
        id="42",
        subject="Test ticket",
        status="open",
        priority="medium",
        requester=TicketRequester(name="Test User"),
        raw=raw,
    )


# ---------------------------------------------------------------------------
# is_overdue
# ---------------------------------------------------------------------------


def test_is_overdue_returns_false_when_due_by_is_absent() -> None:
    """Ticket without due_by is never overdue."""
    ticket = _build_ticket()
    now = datetime.now(timezone.utc)
    assert is_overdue(ticket, now) is False


def test_is_overdue_returns_true_when_due_by_is_in_the_past() -> None:
    """Ticket whose due_by is before now is overdue."""
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    ticket = _build_ticket(due_by=past)
    now = datetime.now(timezone.utc)
    assert is_overdue(ticket, now) is True


def test_is_overdue_returns_false_when_due_by_is_in_the_future() -> None:
    """Ticket whose due_by is after now is not overdue."""
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    ticket = _build_ticket(due_by=future)
    now = datetime.now(timezone.utc)
    assert is_overdue(ticket, now) is False


def test_is_overdue_returns_false_for_malformed_due_by() -> None:
    """Malformed due_by string is silently ignored."""
    ticket = _build_ticket(due_by="not-a-date")
    now = datetime.now(timezone.utc)
    assert is_overdue(ticket, now) is False


# ---------------------------------------------------------------------------
# compute_sla — status derivation
# ---------------------------------------------------------------------------


def test_compute_sla_returns_ok_when_due_by_is_far_in_future() -> None:
    """SLA status is ok when resolution due date is well beyond the risk window."""
    future = (datetime.now(timezone.utc) + AT_RISK_THRESHOLD + timedelta(hours=1)).isoformat()
    ticket = _build_ticket(due_by=future)
    hint = compute_sla(ticket, datetime.now(timezone.utc))
    assert hint.status == "ok"
    assert hint.due_at is not None
    assert hint.minutes_remaining is not None
    assert hint.minutes_remaining > 0


def test_compute_sla_returns_at_risk_when_due_by_is_within_threshold() -> None:
    """SLA status is at_risk when due date falls within the risk window."""
    # 1 hour remaining — inside the 2-hour AT_RISK_THRESHOLD
    near = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    ticket = _build_ticket(due_by=near)
    hint = compute_sla(ticket, datetime.now(timezone.utc))
    assert hint.status == "at_risk"


def test_compute_sla_returns_breached_when_due_by_is_in_the_past() -> None:
    """SLA status is breached when resolution due date has passed."""
    past = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    ticket = _build_ticket(due_by=past)
    hint = compute_sla(ticket, datetime.now(timezone.utc))
    assert hint.status == "breached"
    assert hint.minutes_remaining is not None
    assert hint.minutes_remaining < 0


def test_compute_sla_returns_none_when_no_due_dates_present() -> None:
    """SLA status is none when ticket has no due date information."""
    ticket = _build_ticket()
    hint = compute_sla(ticket, datetime.now(timezone.utc))
    assert hint.status == "none"
    assert hint.due_at is None
    assert hint.minutes_remaining is None


# ---------------------------------------------------------------------------
# compute_sla — is_escalated flag
# ---------------------------------------------------------------------------


def test_compute_sla_returns_breached_when_is_escalated_and_due_in_future() -> None:
    """Escalated resolution SLA is always breached even when deadline is future."""
    future = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
    ticket = _build_ticket(due_by=future, is_escalated=True)
    hint = compute_sla(ticket, datetime.now(timezone.utc))
    assert hint.status == "breached"


def test_compute_sla_keeps_breached_when_is_escalated_and_due_already_passed() -> None:
    """Escalated + already breached ticket remains breached."""
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    ticket = _build_ticket(due_by=past, is_escalated=True)
    hint = compute_sla(ticket, datetime.now(timezone.utc))
    assert hint.status == "breached"


# ---------------------------------------------------------------------------
# compute_sla — first-response SLA precedence
# ---------------------------------------------------------------------------


def test_compute_sla_uses_fr_due_by_when_no_resolution_due() -> None:
    """First-response SLA is used when resolution due date is absent."""
    # fr_due_by far in future → ok
    fr_future = (datetime.now(timezone.utc) + AT_RISK_THRESHOLD + timedelta(hours=1)).isoformat()
    ticket = _build_ticket(fr_due_by=fr_future)
    hint = compute_sla(ticket, datetime.now(timezone.utc))
    assert hint.status == "ok"
    assert hint.due_at is not None


def test_compute_sla_resolution_takes_precedence_over_fr_due() -> None:
    """Resolution due date wins even when first-response date is sooner."""
    now = datetime.now(timezone.utc)
    # fr_due_by is in past (would be breached), due_by is in far future (ok)
    fr_past = (now - timedelta(hours=1)).isoformat()
    res_future = (now + AT_RISK_THRESHOLD + timedelta(hours=2)).isoformat()
    ticket = _build_ticket(due_by=res_future, fr_due_by=fr_past)
    hint = compute_sla(ticket, now)
    # Resolution takes precedence → ok
    assert hint.status == "ok"


def test_compute_sla_fr_escalated_forces_breached() -> None:
    """Escalated first-response SLA is always breached."""
    fr_future = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    ticket = _build_ticket(fr_due_by=fr_future, fr_escalated=True)
    hint = compute_sla(ticket, datetime.now(timezone.utc))
    assert hint.status == "breached"


# ---------------------------------------------------------------------------
# compute_sla — malformed dates
# ---------------------------------------------------------------------------


def test_compute_sla_returns_none_for_malformed_due_by() -> None:
    """Malformed due_by returns status none without raising."""
    ticket = _build_ticket(due_by="totally-invalid")
    hint = compute_sla(ticket, datetime.now(timezone.utc))
    assert hint.status == "none"
