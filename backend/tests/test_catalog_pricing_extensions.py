"""Tests for the pricing-pipeline extensions added alongside the expanded
Cloud Run/Cloud Run functions/Cloud Storage/Persistent Disk/Filestore/
Cloud SQL/AlloyDB/Spanner/Firestore/Bigtable/Memorystore input fields:
region multiplier + rate_by_option resolution in the generic pricing
calculator, the derivation formulas, and the new Persistent Disk/Cloud SQL
line items in PricingEngine."""
from app.catalog.generic_pricing import GenericServicePricingCalculator
from app.catalog.service_catalog_derivations import apply_computed_fields
from app.domain.enums import DiskType, Region
from app.domain.requirements import (
    ComputeRequirement,
    CustomerRequirement,
    DatabaseRequirement,
    ServiceSelection,
    StorageRequirement,
)
from app.services.estimation_service import EstimationService


def make_service(catalog, pricing_provider, settings):
    return EstimationService(catalog=catalog, pricing_provider=pricing_provider, settings=settings)


# -- Generic pricing calculator: region multiplier + rate_by_option --------

def test_region_multiplier_scales_generic_service_cost():
    calc = GenericServicePricingCalculator()
    base_items, _ = calc.calculate(
        [ServiceSelection(service_id="memorystore", config={"tier": "standard-ha", "capacity_gb": 10, "region": "us-central1"})], "USD",
    )
    asia_items, _ = calc.calculate(
        [ServiceSelection(service_id="memorystore", config={"tier": "standard-ha", "capacity_gb": 10, "region": "asia-south1"})], "USD",
    )
    base = next(li for li in base_items if li.sku_id == "memorystore-capacity")
    asia = next(li for li in asia_items if li.sku_id == "memorystore-capacity")
    assert base.monthly_amount == 490.0  # 10 GB x $49.0 (standard-ha rate), us-central1 multiplier 1.0
    assert asia.monthly_amount == round(490.0 * 1.13, 2)  # asia-south1 region multiplier


def test_rate_by_option_prices_storage_class_differently():
    calc = GenericServicePricingCalculator()
    standard, _ = calc.calculate(
        [ServiceSelection(service_id="cloud-storage", config={"storage_class": "standard", "stored_gb": 100})], "USD",
    )
    archive, _ = calc.calculate(
        [ServiceSelection(service_id="cloud-storage", config={"storage_class": "archive", "stored_gb": 100})], "USD",
    )
    standard_storage = next(li for li in standard if li.sku_id == "cloud-storage-storage")
    archive_storage = next(li for li in archive if li.sku_id == "cloud-storage-storage")
    assert standard_storage.monthly_amount == 2.0    # 100 GB x $0.020 (standard)
    assert archive_storage.monthly_amount == 0.12    # 100 GB x $0.0012 (archive) - much cheaper


def test_rate_by_option_falls_back_to_base_price_when_option_missing():
    calc = GenericServicePricingCalculator()
    # No storage_class supplied at all - the dimension must fall back to its
    # own unit_price_usd rather than erroring or pricing at 0.
    line_items, _ = calc.calculate([ServiceSelection(service_id="cloud-storage", config={"stored_gb": 50})], "USD")
    storage = next(li for li in line_items if li.sku_id == "cloud-storage-storage")
    assert storage.monthly_amount == 1.0  # 50 GB x $0.020 base rate


def test_bigtable_storage_type_hdd_cheaper_than_ssd():
    calc = GenericServicePricingCalculator()
    ssd, _ = calc.calculate([ServiceSelection(service_id="bigtable", config={"storage_type": "ssd", "storage_gb": 100, "nodes": 1})], "USD")
    hdd, _ = calc.calculate([ServiceSelection(service_id="bigtable", config={"storage_type": "hdd", "storage_gb": 100, "nodes": 1})], "USD")
    ssd_storage = next(li for li in ssd if li.sku_id == "bigtable-storage")
    hdd_storage = next(li for li in hdd if li.sku_id == "bigtable-storage")
    assert ssd_storage.monthly_amount > hdd_storage.monthly_amount


# -- Derivations -------------------------------------------------------------

def test_cloud_run_request_only_derivation_is_concurrency_adjusted():
    config = apply_computed_fields("cloud-run", {
        "cpu_allocation": "request_only", "vcpu_count": 1, "memory_gb": 2,
        "concurrency": 10, "requests_per_month": 1_000_000, "avg_duration_ms": 200,
    })
    # billable seconds = requests x (duration_s) / concurrency = 1,000,000 x 0.2 / 10 = 20,000
    assert config["vcpu_seconds_per_month"] == 20_000
    assert config["gb_seconds_per_month"] == 40_000  # x memory_gb=2


def test_cloud_run_always_allocated_floors_at_idle_min_instances():
    config = apply_computed_fields("cloud-run", {
        "cpu_allocation": "always_allocated", "vcpu_count": 1, "memory_gb": 1,
        "concurrency": 10, "requests_per_month": 0, "avg_duration_ms": 0,
        "min_instances": 2,
    })
    seconds_per_month = 730 * 3600
    assert config["vcpu_seconds_per_month"] == 2 * seconds_per_month
    assert config["gb_seconds_per_month"] == 2 * seconds_per_month


def test_cloud_run_functions_memory_tier_drives_vcpu():
    config = apply_computed_fields("cloud-run-functions", {
        "memory_mb": "1024", "invocations_per_month": 100_000, "avg_execution_time_ms": 500,
    })
    billable_seconds = 100_000 * 0.5
    assert config["gb_seconds_per_month"] == billable_seconds * 1.0  # 1024 MB = 1 GB
    assert config["vcpu_seconds_per_month"] == billable_seconds * 0.583


def test_spanner_node_mode_converts_to_processing_units():
    config = apply_computed_fields("spanner", {"capacity_mode": "nodes", "node_count": 2})
    assert config["processing_units"] == 2000


def test_spanner_processing_units_mode_is_untouched():
    config = apply_computed_fields("spanner", {"capacity_mode": "processing_units", "processing_units": 300})
    assert config["processing_units"] == 300


def test_alloydb_ram_defaults_to_8gb_per_vcpu_and_read_pool_multiplies():
    config = apply_computed_fields("alloydb", {"vcpu": 4, "read_pool_nodes": 3, "read_pool_vcpu_per_node": 2})
    assert config["ram_gb"] == 32
    assert config["read_pool_total_vcpu"] == 6


def test_alloydb_explicit_ram_is_not_overridden():
    config = apply_computed_fields("alloydb", {"vcpu": 4, "ram_gb": 64})
    assert config["ram_gb"] == 64


# -- Persistent Disk / Cloud SQL legacy path (PricingEngine) ----------------

def test_persistent_disk_provisioned_iops_and_throughput_priced(catalog, pricing_provider, settings):
    service = make_service(catalog, pricing_provider, settings)
    req = CustomerRequirement(
        project_name="Extreme PD workload",
        region=Region.US_CENTRAL1,
        compute=ComputeRequirement(vcpu=2, ram_gb=8),
        storage=StorageRequirement(
            disk_type=DiskType.PD_EXTREME, size_gb=500,
            provisioned_iops=10_000, provisioned_throughput_mbps=500,
        ),
    )
    result = service.generate_estimate(req)
    iops_item = next(li for li in result.cost.line_items if li.sku_id == "disk-provisioned-iops")
    throughput_item = next(li for li in result.cost.line_items if li.sku_id == "disk-provisioned-throughput")
    assert iops_item.monthly_amount > 0
    assert throughput_item.monthly_amount > 0


def test_snapshot_storage_gb_overrides_retention_based_estimate(catalog, pricing_provider, settings):
    service = make_service(catalog, pricing_provider, settings)
    req = CustomerRequirement(
        project_name="Explicit snapshot size",
        region=Region.US_CENTRAL1,
        compute=ComputeRequirement(vcpu=2, ram_gb=8),
        storage=StorageRequirement(
            disk_type=DiskType.PD_BALANCED, size_gb=100,
            snapshot_enabled=True, snapshot_storage_gb=9_999,
        ),
    )
    result = service.generate_estimate(req)
    snap_item = next(li for li in result.cost.line_items if li.sku_id == "snapshot-storage")
    assert snap_item.quantity == 9_999


def test_cloud_sql_hdd_storage_cheaper_than_ssd(catalog, pricing_provider, settings):
    service = make_service(catalog, pricing_provider, settings)

    def _monthly_storage(storage_type):
        req = CustomerRequirement(
            project_name=f"CloudSQL {storage_type}",
            region=Region.US_CENTRAL1,
            database=DatabaseRequirement(required=True, size_gb=100, vcpu=2, ram_gb=8, storage_type=storage_type),
        )
        result = service.generate_estimate(req)
        return next(li for li in result.cost.line_items if li.sku_id == "cloudsql-storage").monthly_amount

    assert _monthly_storage("hdd") < _monthly_storage("ssd")


def test_cloud_sql_backup_and_binlog_storage_priced(catalog, pricing_provider, settings):
    service = make_service(catalog, pricing_provider, settings)
    req = CustomerRequirement(
        project_name="CloudSQL with backups",
        region=Region.US_CENTRAL1,
        database=DatabaseRequirement(required=True, size_gb=50, vcpu=2, ram_gb=8,
                                      backup_storage_gb=200, binary_log_storage_gb=20),
    )
    result = service.generate_estimate(req)
    backup_item = next(li for li in result.cost.line_items if li.sku_id == "cloudsql-backup-storage")
    binlog_item = next(li for li in result.cost.line_items if li.sku_id == "cloudsql-binlog-storage")
    assert backup_item.monthly_amount > 0
    assert binlog_item.monthly_amount > 0


def test_cloud_sql_shared_core_prices_smallest_catalog_tier(catalog, pricing_provider, settings):
    service = make_service(catalog, pricing_provider, settings)
    req = CustomerRequirement(
        project_name="CloudSQL shared-core",
        region=Region.US_CENTRAL1,
        database=DatabaseRequirement(required=True, machine_tier="shared-core", size_gb=10, vcpu=2, ram_gb=8),
    )
    result = service.generate_estimate(req)
    assert result.normalized_spec.database_tier == "db-f1-micro"


def test_cloud_sql_commitment_applies_committed_use_discount(catalog, pricing_provider, settings):
    service = make_service(catalog, pricing_provider, settings)

    def _total(commitment):
        req = CustomerRequirement(
            project_name=f"CloudSQL {commitment}",
            region=Region.US_CENTRAL1,
            database=DatabaseRequirement(required=True, size_gb=0, vcpu=8, ram_gb=32, commitment=commitment),
        )
        return service.generate_estimate(req).cost

    none_cost = _total("none")
    committed_cost = _total("3-year")
    assert committed_cost.discount_total_monthly > 0
    assert committed_cost.total_monthly < none_cost.total_monthly
