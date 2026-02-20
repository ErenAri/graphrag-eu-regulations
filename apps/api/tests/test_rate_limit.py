from app.core.rate_limit import InMemoryRateLimiter, resolve_client_identity


def test_in_memory_rate_limiter_enforces_limit():
    limiter = InMemoryRateLimiter()
    key = "POST:/actions/answer:127.0.0.1"
    assert limiter.allow(key, limit=2, window_seconds=60) is True
    assert limiter.allow(key, limit=2, window_seconds=60) is True
    assert limiter.allow(key, limit=2, window_seconds=60) is False


def test_resolve_client_identity_prefers_forwarded_header_when_enabled():
    headers = {"x-forwarded-for": "203.0.113.9, 198.51.100.2"}
    client_id = resolve_client_identity(headers, client_host="127.0.0.1", trust_proxy=True)
    assert client_id == "203.0.113.9"


def test_resolve_client_identity_falls_back_to_direct_host():
    headers = {"x-forwarded-for": "203.0.113.9"}
    client_id = resolve_client_identity(headers, client_host="127.0.0.1", trust_proxy=False)
    assert client_id == "127.0.0.1"

