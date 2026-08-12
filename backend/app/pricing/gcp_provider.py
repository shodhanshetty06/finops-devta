"""
GcpPricingProvider: live implementation of `PricingProvider` backed by the
real Google Cloud Billing Catalog API. Implements the exact same interface
as `MockGCPPricingProvider` (see `app/pricing/base.py`), so nothing above
this layer - `PricingEngine`, the estimation service, reports - changes when
this is swapped in via `FINOPS_PRICING_PROVIDER=gcp`.

Currency handling: rather than always fetching USD SKUs and re-implementing
FX conversion (which would require maintaining a separate, staled
exchange-rate feed), this provider requests SKUs directly in
`settings.default_currency` via the Catalog API's `currencyCode` parameter -
Google returns `tieredRates` already converted at their own daily rate,
which is both more accurate and simpler than a parallel conversion service.

Sustained/committed use discounts: Google does publish literal SKUs for
committed-use pricing, but they're quoted as an already-discounted effective
hourly rate on a *separate* SKU per family/term/region, not as a percentage
off the on-demand SKU. Precisely resolving and reconciling those SKUs is
left for a future iteration (see `docs/ROADMAP.md` Phase 8: Reserved
Instance / Committed Use recommendation engine). For now this provider
reuses the same flat, publicly-advertised discount percentages the mock
provider uses (~20% SUD, ~25%/45% 1yr/3yr CUD for standard compute
families, per Google's own published guidance) - a deliberate, documented
simplification, not a silent guess.
"""
from __future__ import annotations

from app.core.config import Settings
from app.core.exceptions import PricingProviderError
from app.pricing import mock_data as _discount_reference_data
from app.pricing import sku_matcher as matcher
from app.pricing.base import PricingProvider
from app.pricing.cache import SkuCache
from app.pricing.engine import HOURS_PER_MONTH
from app.pricing.gcp_client import CloudBillingCatalogClient, GcpSku

_COMPUTE_ENGINE_SERVICE = "Compute Engine"
_CLOUD_SQL_SERVICE = "Cloud SQL"
_GKE_SERVICE = "Kubernetes Engine"
_PUBSUB_SERVICE = "Cloud Pub/Sub"
_LOGGING_SERVICE = "Stackdriver Logging"  # Google's Billing Catalog service name predates the "Cloud Logging" rebrand


class GcpPricingProvider(PricingProvider):
    source_name = "gcp_cloud_billing_catalog_api"

    def __init__(self, client: CloudBillingCatalogClient, cache: SkuCache, settings: Settings):
        self._client = client
        self._cache = cache
        self._settings = settings
        self._currency = settings.default_currency

    @classmethod
    def from_settings(cls, settings: Settings, cache: SkuCache) -> "GcpPricingProvider":
        return cls(CloudBillingCatalogClient.from_settings(settings), cache, settings)

    def close(self) -> None:
        self._client.close()

    # -- PricingProvider interface ---------------------------------------

    def get_compute_hourly_price_for_spec(self, vcpu: int, ram_gb: float, family: str, region: str) -> float:
        skus = self._get_skus(_COMPUTE_ENGINE_SERVICE)
        core_price = self._require_price(matcher.find_compute_core_sku(skus, family, region))
        ram_price = self._require_price(matcher.find_compute_ram_sku(skus, family, region))
        return round(vcpu * core_price + ram_gb * ram_price, 6)

    def get_disk_monthly_price_per_gb(self, disk_type: str, region: str) -> float:
        skus = self._get_skus(_COMPUTE_ENGINE_SERVICE)
        return self._require_price(matcher.find_disk_sku(skus, disk_type, region))

    def get_gpu_hourly_price(self, gpu_type: str, region: str) -> float:
        skus = self._get_skus(_COMPUTE_ENGINE_SERVICE)
        return self._require_price(matcher.find_gpu_sku(skus, gpu_type, region))

    def get_cloud_sql_hourly_price(self, tier: str, region: str) -> float:
        skus = self._get_skus(_CLOUD_SQL_SERVICE)
        shape = matcher.parse_cloud_sql_tier(tier)
        if not shape.is_custom:
            return self._require_price(matcher.find_cloud_sql_named_tier_sku(skus, tier, region))
        core_price = self._require_price(matcher.find_cloud_sql_core_sku(skus, region))
        ram_price = self._require_price(matcher.find_cloud_sql_ram_sku(skus, region))
        ram_gb = shape.ram_mb / 1024
        return round(shape.vcpu * core_price + ram_gb * ram_price, 6)

    def get_cloud_sql_storage_monthly_price_per_gb(self, region: str) -> float:
        skus = self._get_skus(_CLOUD_SQL_SERVICE)
        return self._require_price(matcher.find_cloud_sql_storage_sku(skus, region))

    def get_cloud_sql_ha_multiplier(self) -> float:
        # Google prices Cloud SQL HA as a literal doubling of the primary
        # instance's compute+storage cost (a synchronous standby replica in
        # a second zone) rather than as a discrete, separately-priced SKU -
        # this is Google's own documented pricing model, not an
        # approximation, so there is no SKU lookup to perform here.
        return 2.0

    def get_cloud_sql_storage_type_multiplier(self, storage_type: str) -> float:
        # Same modeling choice as get_cloud_sql_ha_multiplier above: Google
        # does not publish HDD Cloud SQL storage as a separately reconcilable
        # discount SKU, so this reuses the flat, publicly-advertised ratio.
        return _discount_reference_data.CLOUD_SQL_STORAGE_TYPE_MULTIPLIER.get(storage_type, 1.0)

    def get_cloud_sql_backup_storage_monthly_price_per_gb(self, region: str) -> float:
        skus = self._get_skus(_CLOUD_SQL_SERVICE)
        return self._require_price(matcher.find_cloud_sql_backup_storage_sku(skus, region))

    def get_disk_provisioned_iops_monthly_price_per_iops(self, region: str) -> float:
        skus = self._get_skus(_COMPUTE_ENGINE_SERVICE)
        return self._require_price(matcher.find_disk_provisioned_iops_sku(skus, region))

    def get_disk_provisioned_throughput_monthly_price_per_mbps(self, region: str) -> float:
        skus = self._get_skus(_COMPUTE_ENGINE_SERVICE)
        return self._require_price(matcher.find_disk_provisioned_throughput_sku(skus, region))

    def get_network_egress_price_per_gb(self, region: str) -> float:
        skus = self._get_skus(_COMPUTE_ENGINE_SERVICE)
        return self._require_price(matcher.find_network_egress_sku(skus, region))

    def get_network_ingress_price_per_gb(self, region: str) -> float:
        # Ingress to Google Cloud is free - Google does not publish a SKU
        # for it at all, so there is nothing to look up.
        return 0.0

    def get_load_balancer_monthly_base_price(self, region: str) -> float:
        skus = self._get_skus(_COMPUTE_ENGINE_SERVICE)
        hourly = self._require_price(matcher.find_load_balancer_sku(skus, region))
        return round(hourly * HOURS_PER_MONTH, 2)

    def get_snapshot_monthly_price_per_gb(self, region: str) -> float:
        skus = self._get_skus(_COMPUTE_ENGINE_SERVICE)
        return self._require_price(matcher.find_snapshot_sku(skus, region))

    def get_gke_cluster_management_hourly_price(self, autopilot: bool) -> float:
        skus = self._get_skus(_GKE_SERVICE)
        return self._require_price(matcher.find_gke_management_sku(skus, autopilot=autopilot))

    def get_gke_enterprise_edition_vcpu_hourly_price(self) -> float:
        # Same modeling choice as get_spot_discount_percent/
        # get_sustained_use_discount_percent below: GKE Enterprise's fleet
        # management fee is not published as a single reconcilable SKU, so
        # this reuses the flat, publicly-advertised approximation.
        return _discount_reference_data.GKE_ENTERPRISE_EDITION_VCPU_HOURLY

    def get_gke_autopilot_pod_vcpu_hourly_price(self, region: str, spot: bool) -> float:
        return (
            _discount_reference_data.GKE_AUTOPILOT_POD_VCPU_SPOT_HOURLY if spot
            else _discount_reference_data.GKE_AUTOPILOT_POD_VCPU_HOURLY
        )

    def get_gke_autopilot_pod_memory_gib_hourly_price(self, region: str, spot: bool) -> float:
        return (
            _discount_reference_data.GKE_AUTOPILOT_POD_MEMORY_GIB_SPOT_HOURLY if spot
            else _discount_reference_data.GKE_AUTOPILOT_POD_MEMORY_GIB_HOURLY
        )

    def get_gke_autopilot_pod_ephemeral_storage_gib_hourly_price(self, region: str, spot: bool) -> float:
        return (
            _discount_reference_data.GKE_AUTOPILOT_POD_EPHEMERAL_STORAGE_GIB_SPOT_HOURLY if spot
            else _discount_reference_data.GKE_AUTOPILOT_POD_EPHEMERAL_STORAGE_GIB_HOURLY
        )

    def get_pubsub_price_per_gib(self, region: str) -> float:
        skus = self._get_skus(_PUBSUB_SERVICE)
        return self._require_price(matcher.find_pubsub_message_delivery_sku(skus))

    def get_pubsub_free_tier_gib_per_month(self) -> float:
        # A documented billing policy allowance, not a Billing Catalog SKU -
        # there is nothing to look up here (see base.py docstring).
        return _discount_reference_data.PUBSUB_FREE_TIER_GIB_PER_MONTH

    def get_logging_price_per_gib(self, region: str) -> float:
        skus = self._get_skus(_LOGGING_SERVICE)
        return self._require_price(matcher.find_logging_volume_sku(skus))

    def get_logging_free_tier_gib_per_month(self) -> float:
        return _discount_reference_data.LOGGING_FREE_TIER_GIB_PER_MONTH

    def get_sustained_use_discount_percent(self) -> float:
        return _discount_reference_data.SUSTAINED_USE_DISCOUNT_PERCENT

    def get_committed_use_discount_percent(self, term_years: int) -> float:
        return _discount_reference_data.COMMITTED_USE_DISCOUNT_PERCENT.get(term_years, 0.0)

    def get_spot_discount_percent(self, family: str) -> float:
        # Same modeling choice as sustained/committed use discounts above:
        # Google's Spot price is a dynamic market rate with no single
        # invoiced "discount percent" SKU to look up, so this reuses the
        # same flat, publicly-advertised approximation the mock provider
        # uses rather than resolving it from Preemptible-usage-type SKUs.
        return _discount_reference_data.SPOT_DISCOUNT_PERCENT.get(family, 60.0)

    def get_os_license_hourly_price(self, operating_system: str, vcpu: int) -> float:
        if operating_system == "linux":
            return 0.0
        skus = self._get_skus(_COMPUTE_ENGINE_SERVICE)
        price = self._require_price(matcher.find_os_license_sku(skus, operating_system))
        if operating_system == "windows_server":
            return round(price * vcpu, 6)
        return price

    def get_local_ssd_monthly_price_per_disk(self, region: str) -> float:
        skus = self._get_skus(_COMPUTE_ENGINE_SERVICE)
        price_per_gb_month = self._require_price(matcher.find_local_ssd_sku(skus, region))
        return round(price_per_gb_month * _discount_reference_data.LOCAL_SSD_SIZE_GB, 2)

    def get_static_ip_monthly_price(self, region: str) -> float:
        skus = self._get_skus(_COMPUTE_ENGINE_SERVICE)
        hourly = self._require_price(matcher.find_static_ip_sku(skus, region))
        return round(hourly * HOURS_PER_MONTH, 2)

    def get_currency(self) -> str:
        return self._currency

    # -- Internal -----------------------------------------------------------

    def _get_skus(self, service_display_name: str) -> list[GcpSku]:
        cached = self._cache.get(service_display_name, self._currency)
        if cached is not None:
            return cached
        service = self._client.find_service(service_display_name)
        skus = self._client.list_skus(service.service_id, currency_code=self._currency)
        self._cache.set(
            service_display_name, self._currency, skus,
            ttl_seconds=self._settings.sku_cache_ttl_seconds,
        )
        return skus

    def _require_price(self, sku: GcpSku) -> float:
        price = sku.base_unit_price(self._currency)
        if price is None:
            raise PricingProviderError(
                f"Matched SKU {sku.sku_id} ({sku.description!r}) has no "
                f"tiered rate published in currency {self._currency!r}."
            )
        return round(price, 6)
