"""Tests for display-currency conversion (app/pricing/currency_converter.py
and the GET /api/v1/currency/rates endpoint). No real network calls are
made anywhere in this file - httpx.MockTransport intercepts every request,
same pattern as tests/test_gcp_client.py."""
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import CurrencyProviderError
from app.main import app
from app.pricing.currency_converter import (
    CurrencyConverter,
    CurrencyExchangeClient,
    InMemoryCurrencyRateCache,
    build_currency_rate_cache,
    get_currency_converter,
)


def _frankfurter_response(base="USD", rates=None, date="2026-08-08"):
    rates = rates or {"INR": 83.12, "EUR": 0.92, "GBP": 0.79}
    return httpx.Response(200, json={"amount": 1.0, "base": base, "date": date, "rates": rates})


# -- CurrencyExchangeClient (HTTP boundary) ----------------------------------

def test_client_parses_a_successful_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["base"] == "USD"
        assert "INR" in request.url.params["symbols"]
        return _frankfurter_response()

    client = CurrencyExchangeClient("https://api.frankfurter.dev/v1/latest", transport=httpx.MockTransport(handler))
    snapshot = client.fetch("USD", ["INR", "EUR", "GBP"])

    assert snapshot.base == "USD"
    assert snapshot.rates["INR"] == 83.12
    assert snapshot.as_of == "2026-08-08"
    assert "frankfurter" in snapshot.source.lower()
    assert snapshot.fetched_at  # a real ISO timestamp was stamped, not left blank


def test_client_retries_transient_5xx_then_succeeds():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 2:
            return httpx.Response(503, text="temporarily unavailable")
        return _frankfurter_response()

    client = CurrencyExchangeClient("https://api.frankfurter.dev/v1/latest", transport=httpx.MockTransport(handler))
    snapshot = client.fetch("USD", ["INR"])
    assert snapshot.rates["INR"] == 83.12
    assert calls["count"] == 2


def test_client_gives_up_after_max_retries_and_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    client = CurrencyExchangeClient("https://api.frankfurter.dev/v1/latest", transport=httpx.MockTransport(handler))
    with pytest.raises(CurrencyProviderError):
        client.fetch("USD", ["INR"])


def test_client_raises_on_malformed_response_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    client = CurrencyExchangeClient("https://api.frankfurter.dev/v1/latest", transport=httpx.MockTransport(handler))
    with pytest.raises(CurrencyProviderError):
        client.fetch("USD", ["INR"])


# -- InMemoryCurrencyRateCache ------------------------------------------------

def test_in_memory_cache_miss_then_hit():
    cache = InMemoryCurrencyRateCache()
    assert cache.get("USD") is None
    client = CurrencyExchangeClient("https://api.frankfurter.dev/v1/latest", transport=httpx.MockTransport(lambda r: _frankfurter_response()))
    snapshot = client.fetch("USD", ["INR"])
    cache.set("USD", snapshot, ttl_seconds=60)
    assert cache.get("USD") == snapshot


def test_in_memory_cache_expires_but_stale_copy_survives():
    cache = InMemoryCurrencyRateCache()
    client = CurrencyExchangeClient("https://api.frankfurter.dev/v1/latest", transport=httpx.MockTransport(lambda r: _frankfurter_response()))
    snapshot = client.fetch("USD", ["INR"])
    cache.set("USD", snapshot, ttl_seconds=0.05)
    assert cache.get("USD") is not None
    time.sleep(0.1)
    assert cache.get("USD") is None  # TTL'd entry is gone...
    assert cache.get_stale("USD") is not None  # ...but the stale fallback copy is still there


def test_build_currency_rate_cache_falls_back_to_in_memory_when_redis_unreachable():
    # Port 1 is reserved and refuses the connection immediately, simulating
    # "Redis is down" without needing a real Redis server (same trick as
    # tests/test_sku_cache.py).
    cache = build_currency_rate_cache("redis://localhost:1/0")
    assert isinstance(cache, InMemoryCurrencyRateCache)


# -- CurrencyConverter (cache + fallback orchestration) -----------------------

def test_converter_fetches_live_on_cache_miss_and_populates_cache():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return _frankfurter_response()

    client = CurrencyExchangeClient("https://api.frankfurter.dev/v1/latest", transport=httpx.MockTransport(handler))
    cache = InMemoryCurrencyRateCache()
    converter = CurrencyConverter(client, cache, ttl_seconds=60, symbols=["INR", "EUR", "GBP"])

    snapshot = converter.get_rates("USD")
    assert snapshot.rates["INR"] == 83.12
    assert calls["count"] == 1

    # second call is served from cache - no second HTTP call
    converter.get_rates("USD")
    assert calls["count"] == 1


def test_converter_falls_back_to_stale_cache_when_live_fetch_fails():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return _frankfurter_response()
        return httpx.Response(503, text="down")

    client = CurrencyExchangeClient("https://api.frankfurter.dev/v1/latest", transport=httpx.MockTransport(handler))
    cache = InMemoryCurrencyRateCache()
    converter = CurrencyConverter(client, cache, ttl_seconds=0.05, symbols=["INR"])

    first = converter.get_rates("USD")
    assert first.stale is False
    time.sleep(0.1)  # let the TTL expire so the next call is forced to try live again

    second = converter.get_rates("USD")
    assert second.stale is True
    assert second.rates["INR"] == 83.12  # still the last real fetched rate, not fabricated


def test_converter_raises_when_live_fetch_fails_and_nothing_is_cached():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    client = CurrencyExchangeClient("https://api.frankfurter.dev/v1/latest", transport=httpx.MockTransport(handler))
    converter = CurrencyConverter(client, InMemoryCurrencyRateCache(), ttl_seconds=60, symbols=["INR"])

    with pytest.raises(CurrencyProviderError):
        converter.get_rates("USD")


def test_convert_same_currency_is_identity_with_no_live_call():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return _frankfurter_response()

    client = CurrencyExchangeClient("https://api.frankfurter.dev/v1/latest", transport=httpx.MockTransport(handler))
    converter = CurrencyConverter(client, InMemoryCurrencyRateCache(), ttl_seconds=60, symbols=["INR"])

    amount, snapshot = converter.convert(128.40, "USD", "USD")
    assert amount == 128.40
    assert calls["count"] == 0


def test_convert_multiplies_by_the_real_fetched_rate():
    client = CurrencyExchangeClient("https://api.frankfurter.dev/v1/latest", transport=httpx.MockTransport(lambda r: _frankfurter_response()))
    converter = CurrencyConverter(client, InMemoryCurrencyRateCache(), ttl_seconds=60, symbols=["INR"])

    amount, snapshot = converter.convert(100.0, "USD", "INR")
    assert amount == 8312.0  # 100 * 83.12, rounded to 2dp
    assert snapshot.rates["INR"] == 83.12


def test_convert_unknown_target_currency_raises_rather_than_guessing():
    client = CurrencyExchangeClient("https://api.frankfurter.dev/v1/latest", transport=httpx.MockTransport(lambda r: _frankfurter_response(rates={"INR": 83.12})))
    converter = CurrencyConverter(client, InMemoryCurrencyRateCache(), ttl_seconds=60, symbols=["INR"])

    with pytest.raises(CurrencyProviderError):
        converter.convert(100.0, "USD", "XYZ")


# -- API endpoint --------------------------------------------------------------

def test_rates_endpoint_returns_live_rates(monkeypatch):
    client = CurrencyExchangeClient("https://api.frankfurter.dev/v1/latest", transport=httpx.MockTransport(lambda r: _frankfurter_response()))
    converter = CurrencyConverter(client, InMemoryCurrencyRateCache(), ttl_seconds=60, symbols=["INR", "EUR", "GBP"])
    app.dependency_overrides[get_currency_converter] = lambda: converter
    try:
        api_client = TestClient(app)
        resp = api_client.get("/api/v1/currency/rates", params={"base": "USD"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["base"] == "USD"
        assert body["rates"]["INR"] == 83.12
        assert body["stale"] is False
        assert "INR" in body["supported_currencies"]
    finally:
        app.dependency_overrides.clear()


def test_rates_endpoint_returns_502_when_live_fetch_fails_and_nothing_cached():
    client = CurrencyExchangeClient("https://api.frankfurter.dev/v1/latest", transport=httpx.MockTransport(lambda r: httpx.Response(503, text="down")))
    converter = CurrencyConverter(client, InMemoryCurrencyRateCache(), ttl_seconds=60, symbols=["INR"])
    app.dependency_overrides[get_currency_converter] = lambda: converter
    try:
        api_client = TestClient(app)
        resp = api_client.get("/api/v1/currency/rates", params={"base": "USD"})
        assert resp.status_code == 502
        assert resp.json()["error"] == "currency_provider_error"
    finally:
        app.dependency_overrides.clear()
