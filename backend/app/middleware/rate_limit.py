"""
Request rate limiting (Phase 7).

A fixed-window counter per client key (IP address) and per minute -
simpler than a true sliding-window/token-bucket algorithm, and sufficient
for this platform's purpose: absorbing accidental retry storms and basic
abuse, not precise traffic shaping. "Heavy" endpoints (estimate generation,
report export, async jobs, intake) get a stricter limit than everything
else, since a single request there costs far more CPU/IO than e.g. a
catalog lookup.

Follows the same Redis-with-automatic-in-memory-fallback pattern as
`app/pricing/cache.py`'s SkuCache: a missing/unreachable Redis degrades to
a per-process counter (loses cross-process sharing, never breaks the app)
rather than failing requests or disabling rate limiting outright.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from functools import lru_cache

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

_WINDOW_SECONDS = 60
_EXEMPT_PATHS = {"/health"}


class RateLimiter(ABC):
    @abstractmethod
    def check(self, key: str, limit: int) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds). Increments the counter
        for `key` regardless of outcome - a rejected request still counts,
        which is what makes this a rate limit and not a quota."""
        ...


class InMemoryRateLimiter(RateLimiter):
    """Per-process fixed-window counter. Thread-unsafe by design, matching
    this platform's single-worker Uvicorn assumption (see SkuCache's same
    note) - fine as a fallback, not a substitute for Redis under real
    concurrent load."""

    def __init__(self) -> None:
        self._counts: dict[str, tuple[int, int]] = {}  # key -> (window_start, count)

    def check(self, key: str, limit: int) -> tuple[bool, int]:
        now = time.time()
        window_start = int(now // _WINDOW_SECONDS)
        stored_window, count = self._counts.get(key, (window_start, 0))
        if stored_window != window_start:
            count = 0
            stored_window = window_start
        count += 1
        self._counts[key] = (stored_window, count)

        retry_after = _WINDOW_SECONDS - int(now % _WINDOW_SECONDS)
        return count <= limit, retry_after


class RedisRateLimiter(RateLimiter):
    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    def check(self, key: str, limit: int) -> tuple[bool, int]:
        now = time.time()
        window_start = int(now // _WINDOW_SECONDS)
        redis_key = f"finops:ratelimit:{window_start}:{key}"

        count = self._redis.incr(redis_key)
        if count == 1:
            self._redis.expire(redis_key, _WINDOW_SECONDS)

        retry_after = _WINDOW_SECONDS - int(now % _WINDOW_SECONDS)
        return count <= limit, retry_after


def build_rate_limiter(redis_url: str) -> RateLimiter:
    try:
        import redis as redis_lib

        client = redis_lib.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        logger.info("RateLimiter: connected to Redis at %s", redis_url)
        return RedisRateLimiter(client)
    except Exception as exc:  # noqa: BLE001 - any failure here means "use the fallback"
        logger.warning(
            "RateLimiter: Redis unreachable (%s); falling back to an in-process "
            "counter. Rate limiting still works, but is not shared across "
            "processes and resets on restart.", exc,
        )
        return InMemoryRateLimiter()


@lru_cache
def get_rate_limiter() -> RateLimiter:
    from app.core.config import get_settings

    return build_rate_limiter(get_settings().redis_url)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        from app.core.config import get_settings

        settings = get_settings()
        if not settings.rate_limit_enabled or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        limiter = get_rate_limiter()
        client_key = request.client.host if request.client else "unknown"

        is_heavy = any(request.url.path.startswith(p) for p in settings.rate_limit_heavy_path_prefixes)
        limit = settings.rate_limit_heavy_requests_per_minute if is_heavy else settings.rate_limit_requests_per_minute
        bucket = "heavy" if is_heavy else "standard"

        allowed, retry_after = limiter.check(f"{bucket}:{client_key}", limit)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "message": f"Rate limit exceeded ({limit} requests/minute for this endpoint). Try again shortly.",
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
