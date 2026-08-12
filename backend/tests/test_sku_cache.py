"""Tests for the SkuCache abstraction: in-memory TTL behavior directly, and
the Redis-vs-fallback selection logic in `build_sku_cache`."""
import time

from app.pricing.cache import InMemorySkuCache, build_sku_cache
from app.pricing.gcp_client import GcpPricingTier, GcpSku


def _sku():
    return GcpSku(
        sku_id="X", description="desc", service_display_name="Compute Engine",
        resource_family="Compute", resource_group="N2Standard", usage_type="OnDemand",
        service_regions=("us-central1",), usage_unit="h",
        tiers=(GcpPricingTier(0, 0.03, "USD"),),
    )


def test_in_memory_cache_miss_then_hit():
    cache = InMemorySkuCache()
    assert cache.get("Compute Engine", "USD") is None
    sku = _sku()
    cache.set("Compute Engine", "USD", [sku], ttl_seconds=60)
    assert cache.get("Compute Engine", "USD") == [sku]


def test_in_memory_cache_is_keyed_by_currency():
    cache = InMemorySkuCache()
    cache.set("Compute Engine", "USD", [_sku()], ttl_seconds=60)
    assert cache.get("Compute Engine", "EUR") is None


def test_in_memory_cache_expires_after_ttl():
    cache = InMemorySkuCache()
    cache.set("Compute Engine", "USD", [_sku()], ttl_seconds=0.05)
    assert cache.get("Compute Engine", "USD") is not None
    time.sleep(0.1)
    assert cache.get("Compute Engine", "USD") is None


def test_build_sku_cache_falls_back_to_in_memory_when_redis_unreachable():
    # Port 1 is reserved and will refuse the connection immediately/quickly,
    # simulating "Redis is down" without needing a real Redis server.
    cache = build_sku_cache("redis://localhost:1/0")
    assert isinstance(cache, InMemorySkuCache)
    # Falls back but is still fully functional as a cache.
    cache.set("Compute Engine", "USD", [_sku()], ttl_seconds=60)
    assert cache.get("Compute Engine", "USD") is not None
