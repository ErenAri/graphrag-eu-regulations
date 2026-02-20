import time
from collections import defaultdict, deque
from collections.abc import Mapping
from typing import Protocol

import redis


class RateLimiter(Protocol):
    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        ...


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._requests: defaultdict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        bucket = self._requests[key]
        cutoff = now - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


class RedisRateLimiter:
    def __init__(self, redis_url: str, prefix: str = "sat-graph-rag", timeout_seconds: float = 1.0):
        self._client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=timeout_seconds,
            socket_connect_timeout=timeout_seconds,
        )
        self._prefix = prefix

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        bucket_index = int(time.time()) // window_seconds
        bucket_key = f"{self._prefix}:{key}:{bucket_index}"
        pipeline = self._client.pipeline()
        pipeline.incr(bucket_key, 1)
        pipeline.expire(bucket_key, window_seconds + 5)
        count_raw, _ = pipeline.execute()
        count = int(count_raw)
        return count <= limit


def resolve_client_identity(
    headers: Mapping[str, str],
    client_host: str | None,
    trust_proxy: bool,
) -> str:
    if trust_proxy:
        forwarded = headers.get("x-forwarded-for")
        if forwarded:
            first_hop = forwarded.split(",", 1)[0].strip()
            if first_hop:
                return first_hop
    return client_host or "unknown"
