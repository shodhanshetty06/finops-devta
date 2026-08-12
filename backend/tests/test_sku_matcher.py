"""Tests for sku_matcher.py against hand-built SKU fixtures shaped like real
Cloud Billing Catalog API responses, including decoys (wrong region, wrong
usage type, custom-machine-type variants, wrong resource family) that a
naive keyword match would incorrectly select - each test asserts the
correct SKU wins over its decoy."""
import pytest

from app.core.exceptions import PricingProviderError
from app.pricing import sku_matcher as m
from app.pricing.gcp_client import GcpPricingTier, GcpSku


def _sku(description, *, family="Compute", group="", usage="OnDemand",
         regions=("us-central1",), price=0.05, service="Compute Engine"):
    return GcpSku(
        sku_id=description[:12],
        description=description,
        service_display_name=service,
        resource_family=family,
        resource_group=group,
        usage_type=usage,
        service_regions=tuple(regions),
        usage_unit="h",
        tiers=(GcpPricingTier(0, price, "USD"),),
    )


# -- Compute core/RAM ------------------------------------------------------

COMPUTE_FIXTURES = [
    _sku("N2 Instance Core running in Americas", regions=["us-central1", "us-east1"], price=0.031),
    _sku("N2 Instance Ram running in Americas", regions=["us-central1", "us-east1"], price=0.0042),
    _sku("N2 Custom Instance Core running in Americas", price=0.999),  # decoy: custom, not predefined
    _sku("Preemptible N2 Instance Core running in Americas", usage="Preemptible", price=0.01),  # decoy: wrong usage type
    _sku("N2 Instance Core running in EMEA", regions=["europe-west1"], price=0.034),  # decoy: wrong region
    _sku("E2 Instance Core running in Americas", price=0.021),
    _sku("E2 Instance Ram running in Americas", price=0.0028),
    _sku("N2D AMD Instance Core running in Americas", price=0.0271),
    _sku("Compute optimized Core running in Americas", price=0.0348),
    _sku("A2 Instance Core running in Americas", price=0.0315),
]


@pytest.mark.parametrize("family,expected_price", [
    ("n2", 0.031), ("e2", 0.021), ("n2d", 0.0271), ("c2", 0.0348), ("a2", 0.0315),
])
def test_find_compute_core_sku_selects_correct_family(family, expected_price):
    sku = m.find_compute_core_sku(COMPUTE_FIXTURES, family, "us-central1")
    assert sku.base_unit_price() == pytest.approx(expected_price)


def test_find_compute_ram_sku_ignores_core_line():
    sku = m.find_compute_ram_sku(COMPUTE_FIXTURES, "n2", "us-central1")
    assert sku.base_unit_price() == pytest.approx(0.0042)


def test_find_compute_core_sku_excludes_custom_and_preemptible_decoys():
    sku = m.find_compute_core_sku(COMPUTE_FIXTURES, "n2", "us-central1")
    assert "custom" not in sku.description.lower()
    assert sku.usage_type == "OnDemand"


def test_find_compute_core_sku_respects_region():
    sku = m.find_compute_core_sku(COMPUTE_FIXTURES, "n2", "us-east1")
    assert sku.base_unit_price() == pytest.approx(0.031)  # same Americas SKU covers us-east1 too
    with pytest.raises(PricingProviderError):
        m.find_compute_core_sku(COMPUTE_FIXTURES, "n2", "asia-south1")


def test_find_compute_core_sku_unknown_family_raises():
    with pytest.raises(PricingProviderError, match="No SKU matching rule"):
        m.find_compute_core_sku(COMPUTE_FIXTURES, "m1-ultramega", "us-central1")


# -- Disks -------------------------------------------------------------

DISK_FIXTURES = [
    _sku("Storage PD Capacity in us-central1", family="Storage", price=0.04),
    _sku("Regional Storage PD Capacity in us-central1", family="Storage", price=0.08),  # decoy: replicated variant
    _sku("Balanced PD Capacity in us-central1", family="Storage", price=0.10),
    _sku("SSD backed PD Capacity in us-central1", family="Storage", price=0.17),
    _sku("Extreme PD Capacity in us-central1", family="Storage", price=0.125),
    _sku("Storage PD Snapshot in us-central1", family="Storage", price=0.026),  # decoy for disk lookup
]


@pytest.mark.parametrize("disk_type,expected_price", [
    ("pd-standard", 0.04), ("pd-balanced", 0.10), ("pd-ssd", 0.17), ("pd-extreme", 0.125),
])
def test_find_disk_sku(disk_type, expected_price):
    sku = m.find_disk_sku(DISK_FIXTURES, disk_type, "us-central1")
    assert sku.base_unit_price() == pytest.approx(expected_price)
    assert "regional" not in sku.description.lower()
    assert "snapshot" not in sku.description.lower()


def test_find_snapshot_sku():
    sku = m.find_snapshot_sku(DISK_FIXTURES, "us-central1")
    assert sku.base_unit_price() == pytest.approx(0.026)


# -- GPUs -----------------------------------------------------------------

GPU_FIXTURES = [
    _sku("Nvidia Tesla T4 GPU running in Americas", family="GPU", price=0.35),
    _sku("Nvidia L4 GPU running in Americas", family="GPU", price=0.55),
    _sku("Nvidia Tesla A100 GPU running in Americas", family="GPU", price=2.93),
    _sku("Nvidia Tesla V100 GPU running in Americas", family="GPU", price=2.48),
]


@pytest.mark.parametrize("gpu_type,expected_price", [
    ("nvidia-tesla-t4", 0.35), ("nvidia-l4", 0.55), ("nvidia-tesla-a100", 2.93), ("nvidia-tesla-v100", 2.48),
])
def test_find_gpu_sku(gpu_type, expected_price):
    sku = m.find_gpu_sku(GPU_FIXTURES, gpu_type, "us-central1")
    assert sku.base_unit_price() == pytest.approx(expected_price)


# -- Network / load balancer ------------------------------------------------

NETWORK_FIXTURES = [
    # Descriptions verified against a real Cloud Billing Catalog API
    # response (2026-08-12) - Google uses "Standard Data Transfer Out to
    # Internet from <city>", not "Internet Egress".
    _sku("Network Standard Data Transfer Out to Internet from Iowa", family="Network", price=0.12),
    _sku("Network Vpn Internet Data Transfer Out from Iowa to Americas", family="Network", price=0.19),  # decoy: VPN variant
    _sku("Network Load Balancing: Forwarding Rule x hour", family="Network", price=0.025),
]


def test_find_network_egress_sku_excludes_premium_tier():
    sku = m.find_network_egress_sku(NETWORK_FIXTURES, "us-central1")
    assert sku.base_unit_price() == pytest.approx(0.12)


def test_find_load_balancer_sku():
    sku = m.find_load_balancer_sku(NETWORK_FIXTURES, "us-central1")
    assert sku.base_unit_price() == pytest.approx(0.025)


# -- GKE ---------------------------------------------------------------

GKE_FIXTURES = [
    # Descriptions verified against a real Cloud Billing Catalog API
    # response (2026-08-12) - Google uses "Zonal/Regional/Autopilot
    # Kubernetes Clusters", not "Cluster Management Fee".
    _sku("Zonal Kubernetes Clusters", family="ApplicationServices", price=0.10),
    _sku("Regional Kubernetes Clusters", family="ApplicationServices", price=0.10),  # decoy: regional, not matched (see sku_matcher.py note)
    _sku("Autopilot Kubernetes Clusters", family="ApplicationServices", price=0.10),
]


# -- Pub/Sub -------------------------------------------------------------

PUBSUB_FIXTURES = [
    _sku("Message Delivery Basic", family="Network", service="Cloud Pub/Sub", regions=[], price=0.0390625),
    _sku("Message Delivery Basic - Inter-region", family="Network", service="Cloud Pub/Sub", regions=[], price=0.06),  # decoy: pricier inter-region variant
    _sku("Snapshot Storage", family="Storage", service="Cloud Pub/Sub", regions=[], price=0.27),  # decoy: unrelated dimension
]


def test_find_pubsub_message_delivery_sku_prefers_shortest_description():
    sku = m.find_pubsub_message_delivery_sku(PUBSUB_FIXTURES)
    assert sku.description == "Message Delivery Basic"
    assert sku.base_unit_price() == pytest.approx(0.0390625)


def test_find_pubsub_message_delivery_sku_raises_when_missing():
    with pytest.raises(PricingProviderError):
        m.find_pubsub_message_delivery_sku([s for s in PUBSUB_FIXTURES if "Snapshot" in s.description])


# -- Cloud Logging ---------------------------------------------------------

LOGGING_FIXTURES = [
    _sku("Log Volume", family="Analysis", service="Stackdriver Logging", regions=[], price=0.50),
    _sku("Log Bucket Storage", family="Storage", service="Stackdriver Logging", regions=[], price=0.01),  # decoy: unrelated dimension
]


def test_find_logging_volume_sku():
    sku = m.find_logging_volume_sku(LOGGING_FIXTURES)
    assert sku.description == "Log Volume"
    assert sku.base_unit_price() == pytest.approx(0.50)


def test_find_logging_volume_sku_raises_when_missing():
    with pytest.raises(PricingProviderError):
        m.find_logging_volume_sku([s for s in LOGGING_FIXTURES if "Bucket" in s.description])


def test_find_gke_management_sku_standard_vs_autopilot():
    standard = m.find_gke_management_sku(GKE_FIXTURES, autopilot=False)
    autopilot = m.find_gke_management_sku(GKE_FIXTURES, autopilot=True)
    assert "zonal" in standard.description.lower()
    assert "autopilot" in autopilot.description.lower()


# -- Cloud SQL ---------------------------------------------------------

CLOUD_SQL_FIXTURES = [
    _sku("Cloud SQL for MySQL: Micro instance", family="ApplicationServices", service="Cloud SQL", price=0.015),
    _sku("Cloud SQL for MySQL: Small instance", family="ApplicationServices", service="Cloud SQL", price=0.05),
    _sku("Cloud SQL for MySQL: Custom vCPU in Americas", family="ApplicationServices", service="Cloud SQL", price=0.0413),
    _sku("Cloud SQL for MySQL: Custom RAM in Americas", family="ApplicationServices", service="Cloud SQL", price=0.007),
    _sku("Cloud SQL for MySQL: SSD storage in Americas", family="ApplicationServices", service="Cloud SQL", price=0.17),
]


def test_parse_cloud_sql_tier_named():
    shape = m.parse_cloud_sql_tier("db-f1-micro")
    assert shape.is_custom is False
    assert shape.named_keyword == "Micro"


def test_parse_cloud_sql_tier_custom():
    shape = m.parse_cloud_sql_tier("db-custom-4-16384")
    assert shape.is_custom is True
    assert shape.vcpu == 4
    assert shape.ram_mb == 16384


def test_parse_cloud_sql_tier_invalid_raises():
    with pytest.raises(PricingProviderError):
        m.parse_cloud_sql_tier("not-a-real-tier")


def test_find_cloud_sql_named_tier_sku():
    sku = m.find_cloud_sql_named_tier_sku(CLOUD_SQL_FIXTURES, "db-f1-micro", "us-central1")
    assert sku.base_unit_price() == pytest.approx(0.015)


def test_find_cloud_sql_custom_core_and_ram_skus():
    core = m.find_cloud_sql_core_sku(CLOUD_SQL_FIXTURES, "us-central1")
    ram = m.find_cloud_sql_ram_sku(CLOUD_SQL_FIXTURES, "us-central1")
    assert core.base_unit_price() == pytest.approx(0.0413)
    assert ram.base_unit_price() == pytest.approx(0.007)


def test_find_cloud_sql_storage_sku():
    sku = m.find_cloud_sql_storage_sku(CLOUD_SQL_FIXTURES, "us-central1")
    assert sku.base_unit_price() == pytest.approx(0.17)


# -- OS Licensing ---------------------------------------------------------

LICENSE_FIXTURES = [
    _sku("Licensing Fee for Windows Server 2022 Datacenter (CPU cost)", family="Licensing", regions=[], price=0.04),
    _sku("Licensing Fee for Red Hat Enterprise Linux (CPU cost)", family="Licensing", regions=[], price=0.06),
    _sku("Licensing Fee for SUSE Linux Enterprise Server", family="Licensing", regions=[], price=0.02),
    _sku("Licensing Fee for Windows Server 2022 Datacenter (additional RAM-based cost)", family="Licensing", regions=[], price=0.006),  # decoy: RAM-based variant, longer description loses the tie-break
]


@pytest.mark.parametrize("operating_system,expected_price", [
    ("windows_server", 0.04), ("rhel", 0.06), ("suse", 0.02),
])
def test_find_os_license_sku(operating_system, expected_price):
    sku = m.find_os_license_sku(LICENSE_FIXTURES, operating_system)
    assert sku.base_unit_price() == pytest.approx(expected_price)


def test_find_os_license_sku_unknown_os_raises():
    with pytest.raises(PricingProviderError, match="No SKU matching rule"):
        m.find_os_license_sku(LICENSE_FIXTURES, "not-an-os")


def test_find_os_license_sku_ignores_region_since_licensing_is_global():
    # No serviceRegions filter is applied - a global SKU (regions=[]) must
    # still resolve regardless of what region is asked about elsewhere.
    sku = m.find_os_license_sku(LICENSE_FIXTURES, "windows_server")
    assert sku.service_regions == ()


# -- Local SSD / static IP -------------------------------------------------

LOCAL_SSD_FIXTURES = [
    _sku("SSD backed Local Storage in us-central1", family="Storage", price=0.080),
    _sku("SSD backed Local Storage in europe-west1", family="Storage", regions=["europe-west1"], price=0.090),
]

STATIC_IP_FIXTURES = [
    _sku("Static Ip Charge", family="Network", regions=["us-central1"], price=0.010),
    _sku("Static Ip Charge on a Standby VM", family="Network", regions=["europe-west1"], price=0.012),  # decoy: different region
]


def test_find_local_ssd_sku_respects_region():
    sku = m.find_local_ssd_sku(LOCAL_SSD_FIXTURES, "us-central1")
    assert sku.base_unit_price() == pytest.approx(0.080)


def test_find_static_ip_sku_respects_region():
    sku = m.find_static_ip_sku(STATIC_IP_FIXTURES, "us-central1")
    assert sku.base_unit_price() == pytest.approx(0.010)
    with pytest.raises(PricingProviderError):
        m.find_static_ip_sku(STATIC_IP_FIXTURES, "asia-south1")


# -- Ambiguity tie-break -------------------------------------------------

def test_ambiguous_matches_prefer_shortest_description():
    fixtures = [
        _sku("N2 Instance Core running in Americas", price=0.031),
        _sku("N2 Instance Core running in Americas (reservation-bound)", price=0.028),
    ]
    sku = m.find_compute_core_sku(fixtures, "n2", "us-central1")
    assert sku.description == "N2 Instance Core running in Americas"


def test_no_match_raises_with_actionable_message():
    with pytest.raises(PricingProviderError, match="No Cloud Billing Catalog SKU matched"):
        m.find_compute_core_sku([], "n2", "us-central1")
