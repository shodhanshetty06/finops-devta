"""Unit tests for the Phase 9 Azure mock catalog/pricing providers - see
test_aws_provider.py for the equivalent AWS coverage; both follow the same
canonical-vocabulary contract."""
import pytest

from app.catalog.azure_provider import AzureCatalogProvider
from app.pricing.azure_provider import AzurePricingProvider


@pytest.fixture
def catalog():
    return AzureCatalogProvider()


@pytest.fixture
def pricing():
    return AzurePricingProvider()


def test_list_machine_types_filters_by_canonical_family(catalog):
    n2_types = catalog.list_machine_types(family="n2")
    assert len(n2_types) > 0
    assert all(m.family == "n2" for m in n2_types)
    assert all(m.name.startswith("Standard_D") for m in n2_types)


def test_list_machine_types_covers_every_canonical_family(catalog):
    for family in ("e2", "n2", "n2d", "c2", "a2"):
        types = catalog.list_machine_types(family=family)
        assert len(types) > 0, f"no Azure machine types mapped for canonical family '{family}'"


def test_gpu_family_machine_types_flag_supports_gpu(catalog):
    a2_types = catalog.list_machine_types(family="a2")
    assert all(m.supports_gpu for m in a2_types)


def test_disk_type_names_are_canonical_codes(catalog):
    names = {d.name for d in catalog.list_disk_types()}
    assert names == {"pd-standard", "pd-balanced", "pd-ssd", "pd-extreme"}
    premium = next(d for d in catalog.list_disk_types() if d.name == "pd-ssd")
    assert "premium" in premium.description.lower()


def test_region_support_uses_canonical_region_codes(catalog):
    assert catalog.is_region_supported("europe-west1") is True
    assert catalog.is_region_supported("asia-south1") is True
    assert catalog.is_region_supported("not-a-real-region") is False
    # Real Azure region names are NOT the lookup key - only canonical codes are.
    assert catalog.is_region_supported("westeurope") is False


def test_compute_pricing_scales_with_vcpu_and_ram(pricing):
    small = pricing.get_compute_hourly_price_for_spec(vcpu=2, ram_gb=8, family="n2", region="us-central1")
    large = pricing.get_compute_hourly_price_for_spec(vcpu=16, ram_gb=64, family="n2", region="us-central1")
    assert small > 0
    assert large > small


def test_disk_and_gpu_pricing_positive(pricing):
    assert pricing.get_disk_monthly_price_per_gb("pd-ssd", "us-central1") > 0
    assert pricing.get_gpu_hourly_price("nvidia-tesla-a100", "us-central1") > 0


def test_unknown_gpu_type_raises(pricing):
    with pytest.raises(KeyError):
        pricing.get_gpu_hourly_price("not-a-gpu", "us-central1")


def test_azure_has_no_sustained_use_discount(pricing):
    assert pricing.get_sustained_use_discount_percent() == 0.0


def test_azure_committed_use_discount_available(pricing):
    assert pricing.get_committed_use_discount_percent(1) > 0
    assert pricing.get_committed_use_discount_percent(3) > pricing.get_committed_use_discount_percent(1)


def test_source_name_identifies_azure(pricing):
    assert pricing.source_name == "azure_mock_catalog"


def test_spot_discount_percent_is_positive_for_every_family(pricing):
    for family in ("e2", "n2", "n2d", "c2", "a2"):
        assert pricing.get_spot_discount_percent(family) > 0
    assert pricing.get_spot_discount_percent("not-a-family") > 0  # falls back to a default, never raises


def test_os_license_hourly_price_zero_for_linux_positive_for_others(pricing):
    assert pricing.get_os_license_hourly_price("linux", vcpu=4) == 0.0
    assert pricing.get_os_license_hourly_price("windows_server", vcpu=4) > 0
    assert pricing.get_os_license_hourly_price("suse", vcpu=4) > 0


def test_local_ssd_and_static_ip_prices_are_positive(pricing):
    assert pricing.get_local_ssd_monthly_price_per_disk("us-central1") > 0
    assert pricing.get_static_ip_monthly_price("us-central1") > 0
