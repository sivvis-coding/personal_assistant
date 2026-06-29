from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime.

    Parameters:
        None.

    Returns:
        Current UTC datetime with timezone information.

    Edge cases:
        None.
    """
    return datetime.now(timezone.utc)
