"""Async rate limiting and retry helpers for bulk Freshservice harvesting.

Nothing in the live integration path enforces request pacing or 429 handling;
these helpers exist specifically for the Insights history archive, which fans
out many requests against Freshservice's per-minute rate limit.
"""

import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)

# Backoff schedule (seconds) used when Freshservice returns 429 without a usable
# Retry-After header. Doubles up to a ceiling so a rate-limited harvest recovers
# instead of hammering the API.
_BACKOFF_SECONDS = [2, 4, 8, 16]


class AsyncRateLimiter:
    """Enforce a minimum interval between requests across concurrent callers.

    Parameters:
        rate_per_min: Maximum requests per minute. Values <= 0 disable limiting.

    Returns:
        Rate limiter shared by every request issued during a harvest.

    Edge cases:
        A single lock serializes the timestamp bookkeeping only; the awaited
        sleep happens while holding the lock so callers are paced fairly.
    """

    def __init__(self, rate_per_min: int) -> None:
        self._min_interval = 60.0 / rate_per_min if rate_per_min > 0 else 0.0
        self._lock = asyncio.Lock()
        self._last_call: float = 0.0

    async def acquire(self) -> None:
        """Block until enough time has passed since the previous request.

        Parameters:
            None.

        Returns:
            None once the caller is allowed to proceed.

        Edge cases:
            With limiting disabled (rate_per_min <= 0) this returns immediately.
        """
        if self._min_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    rate_limiter: AsyncRateLimiter | None = None,
    max_retries: int = len(_BACKOFF_SECONDS),
    **kwargs,
) -> httpx.Response:
    """Issue an HTTP request, honoring rate limiting and 429/Retry-After backoff.

    Parameters:
        client: Shared httpx client.
        method: HTTP method (e.g. "GET").
        url: Absolute request URL.
        rate_limiter: Optional limiter acquired before each attempt.
        max_retries: Maximum number of retries on HTTP 429.
        **kwargs: Passed through to httpx (params, auth, json, ...).

    Returns:
        The first non-429 response (caller decides how to handle its status).

    Edge cases:
        A Retry-After header (when present and numeric) overrides the backoff
        schedule. After exhausting retries the last 429 response is returned so
        the caller can raise_for_status as usual.
    """
    attempt = 0
    while True:
        if rate_limiter is not None:
            await rate_limiter.acquire()
        response = await client.request(method, url, **kwargs)
        if response.status_code != 429 or attempt >= max_retries:
            return response
        delay = _retry_after_seconds(response) or _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]
        logger.warning("Freshservice 429 on %s — backing off %ss (attempt %d)", url, delay, attempt + 1)
        await asyncio.sleep(delay)
        attempt += 1


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Parse a numeric Retry-After header into seconds, or None when absent/invalid."""
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None
