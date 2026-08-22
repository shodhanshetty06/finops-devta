"""
Display-currency conversion (independent of pricing).

Every estimate is *priced* in a single native currency (`Settings.default_currency`,
USD for the mock provider) - that number never changes, and this module has
nothing to do with computing it. What this module does is answer a
different, purely presentational question: "what is $128.40/month in
rupees, as of right now?" - so a customer can view an already-computed
estimate in their own currency without anything being re-priced.

Rates come from Frankfurter (https://www.frankfurter.dev), a free API with
no key required that republishes the European Central Bank's daily
reference rates. This is the *only* place in the codebase that talks to it.

Caching mirrors app/pricing/cache.py's SkuCache exactly on purpose (same
two backends, same fallback behavior, same reasoning) - exchange rates
don't need to be fetched more than a few times a day, and a Redis outage
must not break the app, just lose cross-process sharing.

Failure handling is deliberately layered so a rate is never fabricated:
1. Try the live API.
2. On failure, fall back to the last cached value for that currency pair,
   however old it is (a real historical rate, clearly timestamped, beats no
   rate at all).
3. Only if there is truly no cached value either does this raise
   CurrencyProviderError - conversion is simply unavailable, never guessed.
"""
from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache

import httpx

from app.core.exceptions import CurrencyProviderError
from app.domain.estimate import EstimateResult

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 0.5
_REQUEST_TIMEOUT_SECONDS = 8.0


@dataclass(frozen=True)
class ExchangeRateSnapshot:
    """Rates for converting `base` into each currency in `rates`, as of
    `as_of` (the date the source last published, not the fetch time)."""

    base: str
    rates: dict[str, float]  # currency code -> units of that currency per 1 unit of `base`
    as_of: str  # ISO date, as reported by the source (e.g. "2026-08-08")
    source: str
    fetched_at: str  # ISO datetime this snapshot was actually retrieved (or served from cache since)
    stale: bool = False  # True when served from cache after a failed live refresh attempt

    def to_dict(self) -> dict:
        return {
            "base": self.base,
            "rates": self.rates,
            "as_of": self.as_of,
            "source": self.source,
            "fetched_at": self.fetched_at,
            "stale": self.stale,
        }


def _cache_key(base: str) -> str:
    return f"finops:currency_rates:{base}"


def _serialize(snapshot: ExchangeRateSnapshot) -> str:
    return json.dumps(
        {"base": snapshot.base, "rates": snapshot.rates, "as_of": snapshot.as_of, "source": snapshot.source, "fetched_at": snapshot.fetched_at}
    )


def _deserialize(payload: str) -> ExchangeRateSnapshot:
    raw = json.loads(payload)
    return ExchangeRateSnapshot(base=raw["base"], rates=raw["rates"], as_of=raw["as_of"], source=raw["source"], fetched_at=raw["fetched_at"])


class CurrencyRateCache(ABC):
    @abstractmethod
    def get(self, base: str) -> ExchangeRateSnapshot | None: ...

    @abstractmethod
    def set(self, base: str, snapshot: ExchangeRateSnapshot, *, ttl_seconds: int) -> None: ...

    @abstractmethod
    def get_stale(self, base: str) -> ExchangeRateSnapshot | None:
        """Returns the last known snapshot even if its TTL has expired -
        used only as the last-resort fallback when a live refresh fails."""
        ...


class InMemoryCurrencyRateCache(CurrencyRateCache):
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}  # key -> (expires_at_epoch, serialized_json)
        self._stale_store: dict[str, str] = {}  # key -> serialized_json, never expires on its own

    def get(self, base: str) -> ExchangeRateSnapshot | None:
        key = _cache_key(base)
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, payload = entry
        if time.monotonic() > expires_at:
            return None
        return _deserialize(payload)

    def set(self, base: str, snapshot: ExchangeRateSnapshot, *, ttl_seconds: int) -> None:
        key = _cache_key(base)
        payload = _serialize(snapshot)
        self._store[key] = (time.monotonic() + ttl_seconds, payload)
        self._stale_store[key] = payload

    def get_stale(self, base: str) -> ExchangeRateSnapshot | None:
        payload = self._stale_store.get(_cache_key(base))
        return _deserialize(payload) if payload else None


class RedisCurrencyRateCache(CurrencyRateCache):
    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    def get(self, base: str) -> ExchangeRateSnapshot | None:
        payload = self._redis.get(_cache_key(base))
        return _deserialize(payload) if payload else None

    def set(self, base: str, snapshot: ExchangeRateSnapshot, *, ttl_seconds: int) -> None:
        key = _cache_key(base)
        payload = _serialize(snapshot)
        self._redis.setex(key, ttl_seconds, payload)
        # No-expiry stale copy under a different key, so a fresh-but-expired
        # entry can still be used as a last-resort fallback after the TTL'd
        # key disappears.
        self._redis.set(f"{key}:stale", payload)

    def get_stale(self, base: str) -> ExchangeRateSnapshot | None:
        payload = self._redis.get(f"{_cache_key(base)}:stale")
        return _deserialize(payload) if payload else None


def build_currency_rate_cache(redis_url: str) -> CurrencyRateCache:
    try:
        import redis as redis_lib

        client = redis_lib.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        logger.info("CurrencyRateCache: connected to Redis at %s", redis_url)
        return RedisCurrencyRateCache(client)
    except Exception as exc:  # noqa: BLE001 - any failure here means "use the fallback"
        logger.warning(
            "CurrencyRateCache: Redis unreachable (%s); falling back to an in-process "
            "in-memory cache. Currency conversion will still work, but rates "
            "won't be shared across processes or survive a restart.", exc,
        )
        return InMemoryCurrencyRateCache()


@lru_cache
def get_currency_rate_cache() -> CurrencyRateCache:
    from app.core.config import get_settings

    return build_currency_rate_cache(get_settings().redis_url)


class CurrencyExchangeClient:
    """Talks to the Frankfurter API. Kept separate from CurrencyConverter so
    the HTTP/retry concern and the cache/fallback concern can be tested and
    reasoned about independently (mirrors gcp_client.py's
    CloudBillingCatalogClient vs GcpPricingProvider split).

    `transport` mirrors CloudBillingCatalogClient's same constructor param:
    swap in `httpx.MockTransport` in tests and every call becomes
    deterministic and offline - no real network call, no flaky test."""

    def __init__(self, base_url: str, *, transport: httpx.BaseTransport | None = None) -> None:
        self._base_url = base_url
        self._transport = transport

    def fetch(self, base: str, symbols: list[str]) -> ExchangeRateSnapshot:
        params = {"base": base, "symbols": ",".join(symbols)}
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                with httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS, transport=self._transport) as client:
                    response = client.get(self._base_url, params=params)
                if response.status_code in _RETRYABLE_STATUS_CODES:
                    raise httpx.HTTPStatusError(
                        f"Currency API returned {response.status_code}", request=response.request, response=response,
                    )
                response.raise_for_status()
                body = response.json()
                return ExchangeRateSnapshot(
                    base=body["base"],
                    rates={code: float(rate) for code, rate in body["rates"].items()},
                    as_of=body["date"],
                    source="frankfurter (ECB reference rates)",
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                )
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
        raise CurrencyProviderError(f"Could not fetch live exchange rates: {last_exc}")


class CurrencyConverter:
    """Public entry point: `get_rates()` for the raw snapshot (what the API
    endpoint returns), `convert()` for a single already-priced amount."""

    def __init__(self, client: CurrencyExchangeClient, cache: CurrencyRateCache, *, ttl_seconds: int, symbols: list[str]) -> None:
        self._client = client
        self._cache = cache
        self._ttl_seconds = ttl_seconds
        self._symbols = symbols

    def get_rates(self, base: str = "USD") -> ExchangeRateSnapshot:
        cached = self._cache.get(base)
        if cached is not None:
            return cached

        symbols = [s for s in self._symbols if s != base]
        try:
            fresh = self._client.fetch(base, symbols)
        except CurrencyProviderError:
            stale = self._cache.get_stale(base)
            if stale is not None:
                logger.warning("CurrencyConverter: live fetch failed, serving stale cached rates for base=%s", base)
                return ExchangeRateSnapshot(
                    base=stale.base, rates=stale.rates, as_of=stale.as_of, source=stale.source, fetched_at=stale.fetched_at, stale=True,
                )
            raise

        self._cache.set(base, fresh, ttl_seconds=self._ttl_seconds)
        return fresh

    def convert(self, amount: float, from_currency: str, to_currency: str) -> tuple[float, ExchangeRateSnapshot]:
        if from_currency == to_currency:
            snapshot = ExchangeRateSnapshot(base=from_currency, rates={to_currency: 1.0}, as_of="", source="identity", fetched_at="")
            return round(amount, 2), snapshot
        snapshot = self.get_rates(from_currency)
        rate = snapshot.rates.get(to_currency)
        if rate is None:
            raise CurrencyProviderError(f"No exchange rate available for {from_currency} -> {to_currency}.")
        return round(amount * rate, 2), snapshot

    def convert_estimate(self, estimate: EstimateResult, to_currency: str) -> EstimateResult:
        """Rescales every monetary figure on an already-priced EstimateResult
        into `to_currency` using a single fetched rate - the report-export
        equivalent of the frontend's own display-currency conversion
        (frontend/src/contexts/currency-context.tsx). Nothing is re-priced:
        every figure is still exactly proportional to what the pricing
        engine originally computed, just expressed in a different currency,
        same as viewing the same estimate on screen in INR instead of USD.

        Percentages (tax_rate_percent, support_plan_percent, a discount's
        percent_off) are currency-independent and left untouched - only
        absolute currency amounts are rescaled. Audit log entries are a
        free-text historical record and are not rewritten to a different
        currency; they keep the wording/figures of the currency the
        estimate was actually priced and audited in.

        Returns `estimate` unchanged (no rate fetch at all) when it's
        already priced in `to_currency`. Raises CurrencyProviderError if no
        rate is available - same failure mode as `convert()` - so callers
        that must never fail a report download should catch it and fall
        back to the estimate's native currency, exactly like
        `convert_estimate_currency` below does for the report endpoints."""
        from_currency = estimate.cost.currency
        if from_currency == to_currency:
            return estimate

        snapshot = self.get_rates(from_currency)
        rate = snapshot.rates.get(to_currency)
        if rate is None:
            raise CurrencyProviderError(f"No exchange rate available for {from_currency} -> {to_currency}.")

        def scaled(value: float) -> float:
            return round(value * rate, 2)

        cost = estimate.cost
        converted_cost = cost.model_copy(update={
            "currency": to_currency,
            "line_items": [
                li.model_copy(update={"currency": to_currency, "unit_price": scaled(li.unit_price), "monthly_amount": scaled(li.monthly_amount)})
                for li in cost.line_items
            ],
            "discounts": [d.model_copy(update={"monthly_savings": scaled(d.monthly_savings)}) for d in cost.discounts],
            "resource_summaries": [
                r.model_copy(update={"currency": to_currency, "unit_cost": scaled(r.unit_cost), "subtotal": scaled(r.subtotal)})
                for r in cost.resource_summaries
            ],
            "category_totals": {category: scaled(total) for category, total in cost.category_totals.items()},
            "subtotal_monthly": scaled(cost.subtotal_monthly),
            "discount_total_monthly": scaled(cost.discount_total_monthly),
            "tax_monthly": scaled(cost.tax_monthly),
            "support_monthly": scaled(cost.support_monthly),
            "total_monthly": scaled(cost.total_monthly),
            "total_yearly": scaled(cost.total_yearly),
            "total_three_year": scaled(cost.total_three_year),
        })
        return estimate.model_copy(update={"cost": converted_cost})


def convert_estimate_currency(
    estimate: EstimateResult, target_currency: str | None, converter: CurrencyConverter,
) -> EstimateResult:
    """Shared by every report export route (app/api/routers/reports.py and
    projects.py): converts `estimate` into `target_currency` if given and
    different from the estimate's native pricing currency, via
    `CurrencyConverter.convert_estimate`. Returns `estimate` unchanged, with
    a warning logged, if live/cached rates for that currency aren't
    available - a currency-conversion hiccup must never block a report
    download, same fallback-over-failure philosophy as the rest of this
    module (get_rates() already falls back live -> stale cache; this is one
    layer further out, falling back to "don't convert" as the last resort)."""
    if not target_currency or target_currency == estimate.cost.currency:
        return estimate
    try:
        return converter.convert_estimate(estimate, target_currency)
    except CurrencyProviderError as exc:
        logger.warning(
            "convert_estimate_currency: could not convert to %s, exporting in the estimate's native "
            "currency (%s) instead: %s", target_currency, estimate.cost.currency, exc,
        )
        return estimate


@lru_cache
def get_currency_converter() -> CurrencyConverter:
    from app.core.config import get_settings

    settings = get_settings()
    return CurrencyConverter(
        client=CurrencyExchangeClient(settings.currency_exchange_api_url),
        cache=get_currency_rate_cache(),
        ttl_seconds=settings.currency_exchange_cache_ttl_seconds,
        symbols=settings.supported_display_currencies,
    )
