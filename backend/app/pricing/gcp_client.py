"""
HTTP client for the Google Cloud Billing Catalog API
(https://cloudbilling.googleapis.com/v1). This is the *only* place in the
codebase that speaks HTTP to Google - everything above it (SKU matching,
GcpPricingProvider, the pricing engine) works with plain Python objects
(`GcpService`, `GcpSku`) and never sees a raw response body.

Two auth modes are supported, matching the two options Google actually
offers for this API:

- Service account (OAuth2 bearer token via `google-auth`). Required if the
  org's policy disables API key creation, which is common.
- API key (`?key=...` query param). Lower friction - the Catalog API serves
  public list pricing, so a key scoped to "Cloud Billing API" is sufficient
  and does not require enabling broader OAuth consent.

Exactly one must be configured; `CloudBillingCatalogClient.from_settings()`
picks whichever `Settings` has populated (service account takes precedence
if both are set, since it's the more capable credential).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Iterator

import httpx

from app.core.exceptions import PricingProviderError

logger = logging.getLogger(__name__)

_BASE_URL = "https://cloudbilling.googleapis.com/v1"
_OAUTH_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

# Retry policy: Google's Catalog API is rate-limited and occasionally returns
# transient 5xx errors under load. These are the only statuses worth retrying -
# anything else (401, 403, 404, 400) is a configuration problem that a retry
# can't fix, so it's raised immediately.
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 4
_BACKOFF_BASE_SECONDS = 0.5


@dataclass(frozen=True)
class GcpPricingTier:
    """One row of a tiered-rate pricing schedule. `start_usage_amount` is the
    usage level (in the SKU's usage unit) at which this tier's `unit_price`
    begins to apply - e.g. the first N GB free, then a per-GB rate after."""

    start_usage_amount: float
    unit_price: float
    currency_code: str


@dataclass(frozen=True)
class GcpSku:
    """A single priced SKU as returned by the Catalog API, flattened to the
    fields the pricing/matching layer actually needs. `description` is the
    primary signal SKU-matching logic keys off - Google does not expose a
    stable machine-readable identifier for e.g. "N2 vCPU in us-central1",
    only a human-readable description string that has to be pattern-matched."""

    sku_id: str
    description: str
    service_display_name: str
    resource_family: str
    resource_group: str
    usage_type: str  # "OnDemand", "Preemptible", "Commit1Yr", "Commit3Yr"
    service_regions: tuple[str, ...]
    usage_unit: str
    tiers: tuple[GcpPricingTier, ...]

    def base_unit_price(self, currency_code: str = "USD") -> float | None:
        """Returns the first (lowest `start_usage_amount`) tier's unit price
        in the given currency, which is what this platform's flat
        per-hour/per-GB pricing model needs. Multi-tier volume discounts
        beyond tier 0 are intentionally not modeled - see `docs/ROADMAP.md`
        Phase 8 for tiered/committed pricing depth."""
        matching = [t for t in self.tiers if t.currency_code == currency_code]
        if not matching:
            return None
        return min(matching, key=lambda t: t.start_usage_amount).unit_price

    @classmethod
    def from_api_response(cls, raw: dict[str, Any]) -> "GcpSku":
        category = raw.get("category", {})
        pricing_info = raw.get("pricingInfo", [])
        # Google returns pricingInfo as a list because prices change over
        # time (effectiveTime); the API always returns the currently-active
        # entry first for a `skus.list` call without a time filter.
        expression = pricing_info[0].get("pricingExpression", {}) if pricing_info else {}
        tiers = tuple(
            GcpPricingTier(
                start_usage_amount=float(rate.get("startUsageAmount", 0)),
                unit_price=_money_to_float(rate.get("unitPrice", {})),
                currency_code=rate.get("unitPrice", {}).get("currencyCode", "USD"),
            )
            for rate in expression.get("tieredRates", [])
        )
        return cls(
            sku_id=raw.get("skuId", ""),
            description=raw.get("description", ""),
            service_display_name=category.get("serviceDisplayName", ""),
            resource_family=category.get("resourceFamily", ""),
            resource_group=category.get("resourceGroup", ""),
            usage_type=category.get("usageType", ""),
            service_regions=tuple(raw.get("serviceRegions", [])),
            usage_unit=expression.get("usageUnit", ""),
            tiers=tiers,
        )


@dataclass(frozen=True)
class GcpService:
    """A billable Google Cloud service, e.g. "Compute Engine". SKUs are
    listed per-service, so resolving the service ID is the first API call
    the client makes."""

    service_id: str
    display_name: str

    @classmethod
    def from_api_response(cls, raw: dict[str, Any]) -> "GcpService":
        return cls(service_id=raw.get("serviceId", ""), display_name=raw.get("displayName", ""))


def _money_to_float(money: dict[str, Any]) -> float:
    """Google represents currency as {units: "<whole part as string>", nanos:
    <fractional part, 0-999999999>} to avoid floating-point rounding error in
    transit. E.g. {"units": "0", "nanos": 31611000} == $0.031611. Converted to
    a plain float here since the rest of this codebase already does all its
    own pricing math in float (see `app/pricing/engine.py`), so there's
    nothing to gain from carrying the fixed-point representation further."""
    units = int(money.get("units", 0) or 0)
    nanos = int(money.get("nanos", 0) or 0)
    return units + nanos / 1_000_000_000


class _Authenticator:
    """Wraps either a service-account bearer token or a plain API key behind
    one interface: produce request headers/params. Isolated in its own class
    so `CloudBillingCatalogClient` doesn't need to branch on auth mode at
    every call site."""

    def __init__(self, *, service_account_path: str | None, api_key: str | None):
        if not service_account_path and not api_key:
            raise PricingProviderError(
                "GcpPricingProvider requires either FINOPS_GCP_SERVICE_ACCOUNT_JSON "
                "(path to a service account key file) or FINOPS_GCP_API_KEY to be set."
            )
        self._service_account_path = service_account_path
        self._api_key = api_key
        self._credentials = None  # lazily constructed; only needed for service-account mode

    def auth_kwargs(self) -> dict[str, Any]:
        """Returns kwargs to merge into an httpx request: `headers` for
        service-account bearer auth, `params` for API-key auth."""
        if self._service_account_path:
            token = self._get_bearer_token()
            return {"headers": {"Authorization": f"Bearer {token}"}}
        return {"params": {"key": self._api_key}}

    def _get_bearer_token(self) -> str:
        # Imported lazily so environments that only use API-key auth never
        # need google-auth's transport dependencies to be importable.
        from google.auth.transport.requests import Request as GoogleAuthRequest
        from google.oauth2 import service_account

        if self._credentials is None:
            self._credentials = service_account.Credentials.from_service_account_file(
                self._service_account_path, scopes=_OAUTH_SCOPES,
            )
        if not self._credentials.valid:
            try:
                self._credentials.refresh(GoogleAuthRequest())
            except Exception as exc:  # noqa: BLE001 - re-raised as our own error type below
                raise PricingProviderError(
                    f"Failed to obtain an OAuth2 access token from the configured GCP "
                    f"service account: {exc}"
                ) from exc
        return self._credentials.token


class CloudBillingCatalogClient:
    """Thin, retrying, paginating client over the Cloud Billing Catalog API.

    Deliberately does not cache anything - caching lives one layer up in
    `SkuCache` (see `app/pricing/cache.py`), so this class stays a pure,
    easily-testable HTTP boundary: swap it for a fake transport in tests via
    the `transport` constructor param and every call becomes deterministic
    and offline.
    """

    def __init__(
        self,
        *,
        service_account_path: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self._auth = _Authenticator(service_account_path=service_account_path, api_key=api_key)
        self._client = httpx.Client(base_url=_BASE_URL, timeout=timeout_seconds, transport=transport)

    @classmethod
    def from_settings(cls, settings) -> "CloudBillingCatalogClient":
        return cls(
            service_account_path=settings.gcp_service_account_json,
            api_key=settings.gcp_api_key,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CloudBillingCatalogClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- Public API -----------------------------------------------------

    def find_service(self, display_name: str) -> GcpService:
        """Resolves a human-readable service name (e.g. "Compute Engine")
        to its serviceId, which `list_skus` requires. Services rarely
        change, but this is not cached at this layer - see `SkuCache`,
        which wraps the whole (service + SKU) resolution."""
        for service in self._list_services():
            if service.display_name == display_name:
                return service
        raise PricingProviderError(
            f"Google Cloud Billing Catalog API did not return a service named "
            f"{display_name!r}. This usually means the service account/API key "
            f"lacks the 'Cloud Billing API' scope, or Google renamed the service."
        )

    def list_skus(self, service_id: str, *, currency_code: str = "USD") -> list[GcpSku]:
        """Returns every SKU for a service, following pagination to
        completion. A service can have thousands of SKUs (Compute Engine
        alone is 10,000+), so this always drains all pages - callers should
        go through `SkuCache` rather than calling this on every price
        lookup."""
        skus: list[GcpSku] = []
        for page in self._paginate(
            f"/services/{service_id}/skus",
            params={"currencyCode": currency_code, "pageSize": 5000},
        ):
            skus.extend(GcpSku.from_api_response(raw) for raw in page.get("skus", []))
        return skus

    # -- Internal ---------------------------------------------------------

    def _list_services(self) -> list[GcpService]:
        services: list[GcpService] = []
        for page in self._paginate("/services", params={"pageSize": 200}):
            services.extend(GcpService.from_api_response(raw) for raw in page.get("services", []))
        return services

    def _paginate(self, path: str, *, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        page_token: str | None = None
        while True:
            page_params = dict(params)
            if page_token:
                page_params["pageToken"] = page_token
            page = self._get(path, params=page_params)
            yield page
            page_token = page.get("nextPageToken")
            if not page_token:
                return

    def _get(self, path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        auth_kwargs = self._auth.auth_kwargs()
        merged_params = {**params, **auth_kwargs.get("params", {})}
        headers = auth_kwargs.get("headers", {})

        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = self._client.get(path, params=merged_params, headers=headers)
            except httpx.TransportError as exc:
                last_error = exc
                if attempt == _MAX_RETRIES:
                    break
                self._sleep_before_retry(attempt)
                continue

            if response.status_code == 200:
                return response.json()

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
                logger.warning(
                    "Cloud Billing API returned %s for %s (attempt %d/%d); retrying.",
                    response.status_code, path, attempt + 1, _MAX_RETRIES,
                )
                self._sleep_before_retry(attempt)
                continue

            raise PricingProviderError(
                f"Cloud Billing Catalog API request to {path} failed with "
                f"HTTP {response.status_code}: {response.text[:500]}"
            )

        raise PricingProviderError(
            f"Cloud Billing Catalog API request to {path} failed after "
            f"{_MAX_RETRIES + 1} attempts: {last_error}"
        )

    @staticmethod
    def _sleep_before_retry(attempt: int) -> None:
        time.sleep(_BACKOFF_BASE_SECONDS * (2 ** attempt))
