"""End-to-end tests for GcpPricingProvider: a fake HTTP transport plays the
role of the real Cloud Billing Catalog API (three services - Compute Engine,
Cloud SQL, Kubernetes Engine - each with a realistic SKU list), and every
PricingProvider method is checked against a hand-calculated expected price.
This is the same interface MockGCPPricingProvider implements, so these tests
prove GcpPricingProvider is a drop-in replacement, not just individually
correct methods."""
import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import PricingProviderError
from app.pricing.cache import InMemorySkuCache
from app.pricing.gcp_client import CloudBillingCatalogClient
from app.pricing.gcp_provider import GcpPricingProvider


def _service(service_id, display_name):
    return {"serviceId": service_id, "displayName": display_name}


def _sku(sku_id, description, *, family, group="", usage="OnDemand",
         regions=("us-central1",), price, service_display_name):
    return {
        "skuId": sku_id,
        "description": description,
        "category": {
            "serviceDisplayName": service_display_name,
            "resourceFamily": family,
            "resourceGroup": group,
            "usageType": usage,
        },
        "serviceRegions": list(regions),
        "pricingInfo": [{
            "pricingExpression": {
                "usageUnit": "h",
                "tieredRates": [
                    {"startUsageAmount": 0, "unitPrice": {"currencyCode": "USD", "units": "0", "nanos": int(price * 1_000_000_000) % 1_000_000_000}},
                ] if price < 1 else [
                    {"startUsageAmount": 0, "unitPrice": {"currencyCode": "USD", "units": str(int(price)), "nanos": int(round((price - int(price)) * 1_000_000_000))}},
                ],
            },
        }],
    }


COMPUTE_SKUS = [
    _sku("CE1", "N2 Instance Core running in Americas", family="Compute", price=0.031, service_display_name="Compute Engine"),
    _sku("CE2", "N2 Instance Ram running in Americas", family="Compute", price=0.0042, service_display_name="Compute Engine"),
    _sku("CE3", "Storage PD Capacity in us-central1", family="Storage", price=0.04, service_display_name="Compute Engine"),
    _sku("CE4", "Nvidia Tesla T4 GPU running in Americas", family="GPU", price=0.35, service_display_name="Compute Engine"),
    # Verified against a real Cloud Billing Catalog API response
    # (2026-08-12) - see sku_matcher.py::find_network_egress_sku's docstring.
    _sku("CE5", "Network Standard Data Transfer Out to Internet from Iowa", family="Network", price=0.12, service_display_name="Compute Engine"),
    _sku("CE6", "Network Load Balancing: Forwarding Rule x hour", family="Network", price=0.025, service_display_name="Compute Engine"),
    _sku("CE7", "Storage PD Snapshot in us-central1", family="Storage", price=0.026, service_display_name="Compute Engine"),
    _sku("CE8", "Licensing Fee for Windows Server 2022 Datacenter (CPU cost)", family="Licensing", regions=[], price=0.04, service_display_name="Compute Engine"),
    _sku("CE9", "Licensing Fee for Red Hat Enterprise Linux (CPU cost)", family="Licensing", regions=[], price=0.06, service_display_name="Compute Engine"),
    _sku("CE10", "SSD backed Local Storage in us-central1", family="Storage", price=0.080, service_display_name="Compute Engine"),
    _sku("CE11", "Static Ip Charge", family="Network", price=0.010, service_display_name="Compute Engine"),
]

CLOUD_SQL_SKUS = [
    _sku("SQL1", "Cloud SQL for MySQL: Micro instance", family="ApplicationServices", price=0.015, service_display_name="Cloud SQL"),
    _sku("SQL2", "Cloud SQL for MySQL: Custom vCPU in Americas", family="ApplicationServices", price=0.0413, service_display_name="Cloud SQL"),
    _sku("SQL3", "Cloud SQL for MySQL: Custom RAM in Americas", family="ApplicationServices", price=0.007, service_display_name="Cloud SQL"),
    _sku("SQL4", "Cloud SQL for MySQL: SSD storage in Americas", family="ApplicationServices", price=0.17, service_display_name="Cloud SQL"),
]

GKE_SKUS = [
    # Verified against a real Cloud Billing Catalog API response
    # (2026-08-12) - see sku_matcher.py::find_gke_management_sku's docstring.
    _sku("GKE1", "Zonal Kubernetes Clusters", family="ApplicationServices", price=0.10, service_display_name="Kubernetes Engine"),
    _sku("GKE2", "Autopilot Kubernetes Clusters", family="ApplicationServices", price=0.10, service_display_name="Kubernetes Engine"),
]


def _make_provider() -> GcpPricingProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/services":
            return httpx.Response(200, json={"services": [
                _service("SVC-CE", "Compute Engine"),
                _service("SVC-SQL", "Cloud SQL"),
                _service("SVC-GKE", "Kubernetes Engine"),
            ]})
        if path == "/v1/services/SVC-CE/skus":
            return httpx.Response(200, json={"skus": COMPUTE_SKUS})
        if path == "/v1/services/SVC-SQL/skus":
            return httpx.Response(200, json={"skus": CLOUD_SQL_SKUS})
        if path == "/v1/services/SVC-GKE/skus":
            return httpx.Response(200, json={"skus": GKE_SKUS})
        return httpx.Response(404)

    client = CloudBillingCatalogClient(api_key="fake-key", transport=httpx.MockTransport(handler))
    settings = Settings(FINOPS_GCP_API_KEY="fake-key")
    return GcpPricingProvider(client, InMemorySkuCache(), settings)


def test_compute_hourly_price_combines_core_and_ram_skus():
    provider = _make_provider()
    price = provider.get_compute_hourly_price_for_spec(4, 16, "n2", "us-central1")
    expected = 4 * 0.031 + 16 * 0.0042
    assert price == pytest.approx(expected, rel=1e-4)


def test_disk_and_snapshot_prices():
    provider = _make_provider()
    assert provider.get_disk_monthly_price_per_gb("pd-standard", "us-central1") == pytest.approx(0.04, rel=1e-4)
    assert provider.get_snapshot_monthly_price_per_gb("us-central1") == pytest.approx(0.026, rel=1e-4)


def test_gpu_price():
    provider = _make_provider()
    assert provider.get_gpu_hourly_price("nvidia-tesla-t4", "us-central1") == pytest.approx(0.35, rel=1e-4)


def test_network_egress_and_load_balancer_prices():
    provider = _make_provider()
    assert provider.get_network_egress_price_per_gb("us-central1") == pytest.approx(0.12, rel=1e-4)
    assert provider.get_network_ingress_price_per_gb("us-central1") == 0.0
    lb_monthly = provider.get_load_balancer_monthly_base_price("us-central1")
    assert lb_monthly == pytest.approx(0.025 * 730, rel=1e-4)


def test_cloud_sql_named_tier_price():
    provider = _make_provider()
    assert provider.get_cloud_sql_hourly_price("db-f1-micro", "us-central1") == pytest.approx(0.015, rel=1e-4)


def test_cloud_sql_custom_tier_price_combines_vcpu_and_ram():
    provider = _make_provider()
    price = provider.get_cloud_sql_hourly_price("db-custom-4-16384", "us-central1")
    expected = 4 * 0.0413 + 16 * 0.007  # 16384 MB == 16 GB
    assert price == pytest.approx(expected, rel=1e-4)


def test_cloud_sql_storage_and_ha_multiplier():
    provider = _make_provider()
    assert provider.get_cloud_sql_storage_monthly_price_per_gb("us-central1") == pytest.approx(0.17, rel=1e-4)
    assert provider.get_cloud_sql_ha_multiplier() == 2.0


def test_gke_management_fee_standard_and_autopilot():
    provider = _make_provider()
    assert provider.get_gke_cluster_management_hourly_price(autopilot=False) == pytest.approx(0.10, rel=1e-4)
    assert provider.get_gke_cluster_management_hourly_price(autopilot=True) == pytest.approx(0.10, rel=1e-4)


def test_discounts_reuse_documented_flat_percentages():
    provider = _make_provider()
    assert provider.get_sustained_use_discount_percent() == 20.0
    assert provider.get_committed_use_discount_percent(1) == 25.0
    assert provider.get_committed_use_discount_percent(3) == 45.0
    assert provider.get_committed_use_discount_percent(99) == 0.0


def test_spot_discount_percent_reuses_flat_approximation():
    provider = _make_provider()
    assert provider.get_spot_discount_percent("e2") == 60.0
    assert provider.get_spot_discount_percent("not-a-family") == 60.0  # default fallback


def test_os_license_hourly_price_resolves_real_sku_and_scales_windows_by_vcpu():
    provider = _make_provider()
    assert provider.get_os_license_hourly_price("linux", vcpu=4) == 0.0  # no SKU lookup for free Linux
    assert provider.get_os_license_hourly_price("windows_server", vcpu=4) == pytest.approx(0.04 * 4, rel=1e-4)
    assert provider.get_os_license_hourly_price("rhel", vcpu=4) == pytest.approx(0.06, rel=1e-4)  # flat, not scaled


def test_local_ssd_monthly_price_per_disk():
    provider = _make_provider()
    price = provider.get_local_ssd_monthly_price_per_disk("us-central1")
    assert price == pytest.approx(0.080 * 375, rel=1e-4)


def test_static_ip_monthly_price():
    provider = _make_provider()
    price = provider.get_static_ip_monthly_price("us-central1")
    assert price == pytest.approx(0.010 * 730, rel=1e-4)


def test_currency_defaults_to_settings_default_currency():
    provider = _make_provider()
    assert provider.get_currency() == "USD"


def test_source_name_identifies_live_provider():
    assert GcpPricingProvider.source_name == "gcp_cloud_billing_catalog_api"


def test_results_are_cached_across_calls_same_service():
    call_paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        call_paths.append(request.url.path)
        if request.url.path == "/v1/services":
            return httpx.Response(200, json={"services": [_service("SVC-CE", "Compute Engine")]})
        return httpx.Response(200, json={"skus": COMPUTE_SKUS})

    client = CloudBillingCatalogClient(api_key="k", transport=httpx.MockTransport(handler))
    settings = Settings(FINOPS_GCP_API_KEY="k")
    provider = GcpPricingProvider(client, InMemorySkuCache(), settings)

    provider.get_compute_hourly_price_for_spec(2, 8, "n2", "us-central1")
    calls_after_first = len(call_paths)
    provider.get_disk_monthly_price_per_gb("pd-standard", "us-central1")
    # Second call for the same service (Compute Engine) should be served
    # entirely from cache - no new HTTP calls.
    assert len(call_paths) == calls_after_first


def test_unmatched_sku_raises_pricing_provider_error():
    provider = _make_provider()
    with pytest.raises(PricingProviderError):
        provider.get_compute_hourly_price_for_spec(4, 16, "n2", "antarctica-south1")
