"""
Cache layer for Google Cloud Billing Catalog SKUs.

Fetching every SKU for a service (Compute Engine alone returns 10,000+ rows
across ~3 paginated requests) on every single price lookup would be both
slow and a good way to get rate-limited, so the full per-service SKU list is
fetched once and cached as a unit, keyed by `(service_display_name,
currency_code)`.

Two backends implement the same `SkuCache` interface:

- `RedisSkuCache` - shared across processes/replicas, survives restarts.
  Used when `FINOPS_REDIS_URL` points at a reachable Redis (see
  docker-compose.yml's `redis` service).
- `InMemorySkuCache` - per-process dict with manual TTL expiry. Automatic
  fallback when Redis is unreachable, so a missing/down Redis never breaks
  pricing - it just loses cross-process sharing and restart persistence.

`get_sku_cache()` is the single entry point `GcpPricingProvider` uses; it
never talks to Redis directly, so the fallback logic lives in exactly one
place.
"""
from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import asdict
from functools import lru_cache
from typing import Sequence

from app.pricing.gcp_client import GcpPricingTier, GcpSku

logger = logging.getLogger(__name__)


def _cache_key(service_display_name: str, currency_code: str) -> str:
    return f"finops:sku_cache:{service_display_name}:{currency_code}"


def _serialize(skus: Sequence[GcpSku]) -> str:
    return json.dumps([asdict(sku) for sku in skus])


def _deserialize(payload: str) -> list[GcpSku]:
    raw_list = json.loads(payload)
    return [
        GcpSku(
            sku_id=raw["sku_id"],
            description=raw["description"],
            service_display_name=raw["service_display_name"],
            resource_family=raw["resource_family"],
            resource_group=raw["resource_group"],
            usage_type=raw["usage_type"],
            service_regions=tuple(raw["service_regions"]),
            usage_unit=raw["usage_unit"],
            tiers=tuple(GcpPricingTier(**tier) for tier in raw["tiers"]),
        )
        for raw in raw_list
    ]


class SkuCache(ABC):
    @abstractmethod
    def get(self, service_display_name: str, currency_code: str) -> list[GcpSku] | None:
        """Returns the cached SKU list, or None on a cache miss/expiry."""
        ...

    @abstractmethod
    def set(self, service_display_name: str, currency_code: str, skus: Sequence[GcpSku], *, ttl_seconds: int) -> None:
        ...


class InMemorySkuCache(SkuCache):
    """Per-process dict cache with manual TTL. Thread-unsafe by design - this
    platform runs the API under a single-worker Uvicorn process for now (see
    `docs/ROADMAP.md` Phase 7 for the Celery/multi-worker scale-out plan); if
    that changes, prefer `RedisSkuCache` over adding locking here."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}  # key -> (expires_at_epoch, serialized_json)

    def get(self, service_display_name: str, currency_code: str) -> list[GcpSku] | None:
        key = _cache_key(service_display_name, currency_code)
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, payload = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return _deserialize(payload)

    def set(self, service_display_name: str, currency_code: str, skus: Sequence[GcpSku], *, ttl_seconds: int) -> None:
        key = _cache_key(service_display_name, currency_code)
        self._store[key] = (time.monotonic() + ttl_seconds, _serialize(skus))


class RedisSkuCache(SkuCache):
    """Redis-backed cache. Redis natively supports TTL via `SETEX`, so no
    manual expiry bookkeeping is needed here (unlike `InMemorySkuCache`)."""

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    def get(self, service_display_name: str, currency_code: str) -> list[GcpSku] | None:
        key = _cache_key(service_display_name, currency_code)
        payload = self._redis.get(key)
        if payload is None:
            return None
        return _deserialize(payload)

    def set(self, service_display_name: str, currency_code: str, skus: Sequence[GcpSku], *, ttl_seconds: int) -> None:
        key = _cache_key(service_display_name, currency_code)
        self._redis.setex(key, ttl_seconds, _serialize(skus))


def build_sku_cache(redis_url: str) -> SkuCache:
    """Attempts to construct a working `RedisSkuCache`; falls back to
    `InMemorySkuCache` if Redis is unreachable or the `redis` package can't
    connect within a short timeout. This check happens once at startup
    (result is cached by `get_sku_cache`), not on every request."""
    try:
        import redis as redis_lib

        client = redis_lib.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        logger.info("SkuCache: connected to Redis at %s", redis_url)
        return RedisSkuCache(client)
    except Exception as exc:  # noqa: BLE001 - any failure here means "use the fallback"
        logger.warning(
            "SkuCache: Redis unreachable (%s); falling back to an in-process "
            "in-memory cache. Pricing will still work, but the cache will not "
            "be shared across processes or survive a restart.", exc,
        )
        return InMemorySkuCache()


@lru_cache
def get_sku_cache() -> SkuCache:
    from app.core.config import get_settings

    return build_sku_cache(get_settings().redis_url)
