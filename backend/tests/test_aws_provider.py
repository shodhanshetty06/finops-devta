"""Unit tests for the Phase 9 AWS mock catalog/pricing providers, mirroring
the structure of the GCP mock provider's implicit coverage (via
test_validation.py/test_normalization.py/test_pricing.py) but exercised
directly since these are new, dedicated implementations."""
import pytest

from app.catalog.aws_provider import AwsCatalogProvider
from app.pricing.aws_provider import AwsPricingProvider


@pytest.fixture
def catalog():
    return AwsCatalogProvider()


@pytest.fixture
def pricing():
    return AwsPricingProvider()


def test_list_machine_types_filters_by_canonical_family(catalog):
    e2_types = catalog.list_machine_types(family="e2")
    assert len(e2_types) > 0
    assert all(m.family == "e2" for m in e2_types)
    # Real AWS instance names should appear, not GCP-style names.
    assert all(m.name.startswith("t3.") for m in e2_types)


def test_list_machine_types_covers_every_canonical_family(catalog):
    for family in ("e2", "n2", "n2d", "c2", "a2"):
        types = catalog.list_machine_types(family=family)
        assert len(types) > 0, f"no AWS machine types mapped for canonical family '{family}'"


def test_gpu_family_machine_types_flag_supports_gpu(catalog):
    a2_types = catalog.list_machine_types(family="a2")
    assert all(m.supports_gpu for m in a2_types)


def test_disk_type_names_are_canonical_codes(catalog):
    names = {d.name for d in catalog.list_disk_types()}
    assert names == {"pd-standard", "pd-balanced", "pd-ssd", "pd-extreme"}
    # Real EBS names should be visible in the description instead.
    balanced = next(d for d in catalog.list_disk_types() if d.name == "pd-balanced")
    assert "gp3" in balanced.description.lower() or "ebs" in balanced.description.lower()


def test_gpu_type_names_are_nvidia_chip_names(catalog):
    names = {g.name for g in catalog.list_gpu_types()}
    assert "nvidia-tesla-t4" in names
    assert "nvidia-tesla-a100" in names
    assert all(g.compatible_families == ["a2"] for g in catalog.list_gpu_types())


def test_region_support_uses_canonical_region_codes(catalog):
    assert catalog.is_region_supported("us-central1") is True
    assert catalog.is_region_supported("us-west1") is True
    assert catalog.is_region_supported("not-a-real-region") is False
    # Real AWS region codes are NOT the lookup key - only canonical codes are.
    assert catalog.is_region_supported("us-east-2") is False


def test_cloud_sql_tiers_filter_by_engine(catalog):
    postgres_tiers = catalog.list_cloud_sql_tiers(engine="postgres")
    assert len(postgres_tiers) > 0
    sqlserver_tiers = catalog.list_cloud_sql_tiers(engine="sqlserver")
    assert all(t.vcpu >= 2 for t in sqlserver_tiers)  # db.t3.micro (sqlserver-incompatible) excluded


def test_compute_pricing_scales_with_vcpu_and_ram(pricing):
    small = pricing.get_compute_hourly_price_for_spec(vcpu=2, ram_gb=8, family="n2", region="us-central1")
    large = pricing.get_compute_hourly_price_for_spec(vcpu=8, ram_gb=32, family="n2", region="us-central1")
    assert small > 0
    assert large > small


def test_compute_pricing_applies_region_multiplier(pricing):
    baseline = pricing.get_compute_hourly_price_for_spec(vcpu=4, ram_gb=16, family="n2", region="us-central1")
    pricier_region = pricing.get_compute_hourly_price_for_spec(vcpu=4, ram_gb=16, family="n2", region="asia-southeast1")
    assert pricier_region > baseline


def test_unknown_family_raises(pricing):
    with pytest.raises(KeyError):
        pricing.get_compute_hourly_price_for_spec(vcpu=2, ram_gb=8, family="not-a-family", region="us-central1")


def test_aws_has_no_sustained_use_discount(pricing):
    assert pricing.get_sustained_use_discount_percent() == 0.0


def test_aws_committed_use_discount_available(pricing):
    assert pricing.get_committed_use_discount_percent(1) > 0
    assert pricing.get_committed_use_discount_percent(3) > pricing.get_committed_use_discount_percent(1)


def test_source_name_identifies_aws(pricing):
    assert pricing.source_name == "aws_mock_catalog"


def test_spot_discount_percent_is_positive_for_every_family(pricing):
    for family in ("e2", "n2", "n2d", "c2", "a2"):
        assert pricing.get_spot_discount_percent(family) > 0
    assert pricing.get_spot_discount_percent("not-a-family") > 0  # falls back to a default, never raises


def test_os_license_hourly_price_zero_for_linux_positive_for_others(pricing):
    assert pricing.get_os_license_hourly_price("linux", vcpu=4) == 0.0
    assert pricing.get_os_license_hourly_price("windows_server", vcpu=4) > 0
    assert pricing.get_os_license_hourly_price("rhel", vcpu=4) > 0


def test_windows_license_scales_with_vcpu_rhel_does_not(pricing):
    small = pricing.get_os_license_hourly_price("windows_server", vcpu=2)
    large = pricing.get_os_license_hourly_price("windows_server", vcpu=8)
    assert large == round(small * 4, 6)
    assert pricing.get_os_license_hourly_price("rhel", vcpu=2) == pricing.get_os_license_hourly_price("rhel", vcpu=8)


def test_local_ssd_and_static_ip_prices_are_positive(pricing):
    assert pricing.get_local_ssd_monthly_price_per_disk("us-central1") > 0
    assert pricing.get_static_ip_monthly_price("us-central1") > 0
