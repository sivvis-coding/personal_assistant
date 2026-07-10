import app.integrations.rate_limiter as rl
from app.integrations.rate_limiter import AsyncRateLimiter, request_with_retry


class FakeResponse:
    def __init__(self, status_code: int, headers: dict | None = None) -> None:
        self.status_code = status_code
        self.headers = headers or {}


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def request(self, method: str, url: str, **kwargs) -> FakeResponse:
        self.calls += 1
        return self._responses.pop(0)


def _patch_sleep(monkeypatch) -> list[float]:
    """Replace asyncio.sleep in the module with a recorder; return the log."""
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(rl.asyncio, "sleep", fake_sleep)
    return slept


async def test_rate_limiter_spaces_consecutive_calls(monkeypatch):
    slept = _patch_sleep(monkeypatch)
    limiter = AsyncRateLimiter(60)  # 1s min interval

    await limiter.acquire()  # first call: no wait (last_call is in the far past)
    await limiter.acquire()  # second call: must wait ~1s

    assert slept, "second acquire should sleep"
    assert abs(slept[-1] - 1.0) < 0.2


async def test_rate_limiter_disabled_when_rate_non_positive(monkeypatch):
    slept = _patch_sleep(monkeypatch)
    limiter = AsyncRateLimiter(0)
    await limiter.acquire()
    await limiter.acquire()
    assert slept == []


async def test_request_with_retry_backs_off_then_succeeds(monkeypatch):
    slept = _patch_sleep(monkeypatch)
    client = FakeClient([FakeResponse(429), FakeResponse(429), FakeResponse(200)])

    response = await request_with_retry(client, "GET", "http://x/api", max_retries=3)

    assert response.status_code == 200
    assert client.calls == 3
    assert slept == [2, 4]  # default backoff schedule


async def test_request_with_retry_honors_retry_after(monkeypatch):
    slept = _patch_sleep(monkeypatch)
    client = FakeClient([FakeResponse(429, {"Retry-After": "5"}), FakeResponse(200)])

    response = await request_with_retry(client, "GET", "http://x/api", max_retries=3)

    assert response.status_code == 200
    assert slept == [5.0]


async def test_request_with_retry_returns_last_429_when_exhausted(monkeypatch):
    _patch_sleep(monkeypatch)
    client = FakeClient([FakeResponse(429), FakeResponse(429)])

    response = await request_with_retry(client, "GET", "http://x/api", max_retries=1)

    assert response.status_code == 429
    assert client.calls == 2
