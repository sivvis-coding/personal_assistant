"""Pure SLA computation functions with no I/O.

These helpers are used by TicketService to enrich each Ticket with
SLA state, and by MetricsService to detect overdue tickets.
"""

from datetime import datetime, timedelta, timezone

from app.schemas.ticket import SlaHint, SlaStatus

AT_RISK_THRESHOLD = timedelta(hours=2)


def _parse_iso(value: object) -> datetime | None:
    """Parse an ISO-8601 string into an aware datetime.

    Parameters:
        value: Raw value from the Fresh payload (may be None, non-string, or malformed).

    Returns:
        Aware datetime, or None when parsing fails or value is absent.

    Edge cases:
        Returns None silently for any malformed input — callers must never raise here.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def is_overdue(ticket: object, now: datetime) -> bool:
    """Return whether a ticket is overdue based on raw due_by.

    Replicates the heuristic previously in MetricsService._is_overdue so
    that a single authoritative implementation is shared across services.

    Parameters:
        ticket: Any object with a .raw dict attribute.
        now: Current time (timezone-aware UTC).

    Returns:
        True when due_by is set and the deadline has already passed.

    Edge cases:
        Missing or malformed due_by returns False instead of raising.
    """
    raw = getattr(ticket, "raw", None) or {}
    due = _parse_iso(raw.get("due_by"))
    if due is None:
        return False
    return due < now


def _sla_hint_for_date(due: datetime, now: datetime) -> SlaHint:
    """Derive SlaHint from a single due datetime and the current time.

    Parameters:
        due: Due datetime (timezone-aware).
        now: Current time (timezone-aware UTC).

    Returns:
        SlaHint with ok / at_risk / breached status and minutes_remaining.
    """
    delta = due - now
    minutes_remaining = int(delta.total_seconds() / 60)

    if delta.total_seconds() < 0:
        status: SlaStatus = "breached"
    elif delta <= AT_RISK_THRESHOLD:
        status = "at_risk"
    else:
        status = "ok"

    return SlaHint(status=status, due_at=due, minutes_remaining=minutes_remaining)


def compute_sla(ticket: object, now: datetime) -> SlaHint:
    """Compute SLA state for a ticket.

    Primary SLA: resolution due (due_by / is_escalated).
    First-response SLA: used only when first-response has not yet been sent
    (fr_due_by present and fr_escalated is False or absent).
    If no applicable due date exists, returns SlaStatus 'none'.

    Parameters:
        ticket: Any object with a .raw dict attribute.
        now: Current time (timezone-aware UTC).

    Returns:
        SlaHint reflecting the most relevant SLA deadline.

    Edge cases:
        Never raises — malformed dates fall back to SlaStatus 'none'.
    """
    raw = getattr(ticket, "raw", None) or {}

    # Primary: resolution SLA.
    resolution_due = _parse_iso(raw.get("due_by"))
    is_escalated = bool(raw.get("is_escalated", False))

    if resolution_due is not None:
        hint = _sla_hint_for_date(resolution_due, now)
        # Escalated resolution always counts as breached.
        if is_escalated and hint.status != "breached":
            return SlaHint(
                status="breached",
                due_at=resolution_due,
                minutes_remaining=hint.minutes_remaining,
            )
        return hint

    # Secondary: first-response SLA — only when no first response sent yet.
    fr_due = _parse_iso(raw.get("fr_due_by"))
    fr_escalated = bool(raw.get("fr_escalated", False))

    if fr_due is not None:
        hint = _sla_hint_for_date(fr_due, now)
        if fr_escalated and hint.status != "breached":
            return SlaHint(
                status="breached",
                due_at=fr_due,
                minutes_remaining=hint.minutes_remaining,
            )
        return hint

    return SlaHint(status="none")
