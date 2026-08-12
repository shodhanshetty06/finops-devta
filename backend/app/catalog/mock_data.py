"""
Static reference data describing *valid* Google Cloud configurations.

This mirrors the shape of what the live Cloud Billing Catalog / Compute
Engine API would return. It is deliberately isolated in one module so that
swapping to a live GCP-backed CatalogProvider later touches only
`app/catalog/gcp_provider.py`, never the validation or normalization engines
(which depend on the `CatalogProvider` interface, not this data directly).
"""
from app.catalog.models import (
    CloudSqlTierSpec,
    DiskTypeSpec,
    GkeConfig,
    GpuSpec,
    MachineTypeSpec,
    RegionSpec,
)

MACHINE_TYPES: list[MachineTypeSpec] = [
    # E2 - cost-optimized, no GPU support
    MachineTypeSpec(name="e2-micro", family="e2", vcpu=1, ram_gb=1),
    MachineTypeSpec(name="e2-small", family="e2", vcpu=1, ram_gb=2),
    MachineTypeSpec(name="e2-medium", family="e2", vcpu=1, ram_gb=4),
    MachineTypeSpec(name="e2-standard-2", family="e2", vcpu=2, ram_gb=8),
    MachineTypeSpec(name="e2-standard-4", family="e2", vcpu=4, ram_gb=16),
    MachineTypeSpec(name="e2-standard-8", family="e2", vcpu=8, ram_gb=32),
    MachineTypeSpec(name="e2-standard-16", family="e2", vcpu=16, ram_gb=64),
    MachineTypeSpec(name="e2-standard-32", family="e2", vcpu=32, ram_gb=128),
    # N2 - balanced, general purpose
    MachineTypeSpec(name="n2-standard-2", family="n2", vcpu=2, ram_gb=8),
    MachineTypeSpec(name="n2-standard-4", family="n2", vcpu=4, ram_gb=16),
    MachineTypeSpec(name="n2-standard-8", family="n2", vcpu=8, ram_gb=32),
    MachineTypeSpec(name="n2-standard-16", family="n2", vcpu=16, ram_gb=64),
    MachineTypeSpec(name="n2-standard-32", family="n2", vcpu=32, ram_gb=128),
    MachineTypeSpec(name="n2-standard-48", family="n2", vcpu=48, ram_gb=192),
    MachineTypeSpec(name="n2-standard-64", family="n2", vcpu=64, ram_gb=256),
    # N2D - AMD-based, cost-optimized
    MachineTypeSpec(name="n2d-standard-2", family="n2d", vcpu=2, ram_gb=8),
    MachineTypeSpec(name="n2d-standard-4", family="n2d", vcpu=4, ram_gb=16),
    MachineTypeSpec(name="n2d-standard-8", family="n2d", vcpu=8, ram_gb=32),
    MachineTypeSpec(name="n2d-standard-16", family="n2d", vcpu=16, ram_gb=64),
    # C2 - compute-optimized
    MachineTypeSpec(name="c2-standard-4", family="c2", vcpu=4, ram_gb=16),
    MachineTypeSpec(name="c2-standard-8", family="c2", vcpu=8, ram_gb=32),
    MachineTypeSpec(name="c2-standard-16", family="c2", vcpu=16, ram_gb=64),
    MachineTypeSpec(name="c2-standard-30", family="c2", vcpu=30, ram_gb=120),
    MachineTypeSpec(name="c2-standard-60", family="c2", vcpu=60, ram_gb=240),
    # A2 - GPU-optimized (paired with A100 GPUs)
    MachineTypeSpec(name="a2-highgpu-1g", family="a2", vcpu=12, ram_gb=85, supports_gpu=True),
    MachineTypeSpec(name="a2-highgpu-2g", family="a2", vcpu=24, ram_gb=170, supports_gpu=True),
    MachineTypeSpec(name="a2-highgpu-4g", family="a2", vcpu=48, ram_gb=340, supports_gpu=True),
]

DISK_TYPES: list[DiskTypeSpec] = [
    DiskTypeSpec(name="pd-standard", min_size_gb=10, max_size_gb=65536, description="Standard HDD persistent disk"),
    DiskTypeSpec(name="pd-balanced", min_size_gb=10, max_size_gb=65536, description="Balanced SSD persistent disk"),
    DiskTypeSpec(name="pd-ssd", min_size_gb=10, max_size_gb=65536, description="High-performance SSD persistent disk"),
    DiskTypeSpec(name="pd-extreme", min_size_gb=500, max_size_gb=65536, description="Extreme performance SSD (custom IOPS)"),
]

GPU_TYPES: list[GpuSpec] = [
    GpuSpec(name="nvidia-tesla-t4", max_per_instance=4, compatible_families=["n1", "n2"]),
    GpuSpec(name="nvidia-l4", max_per_instance=8, compatible_families=["g2"]),
    GpuSpec(name="nvidia-tesla-a100", max_per_instance=16, compatible_families=["a2"]),
    GpuSpec(name="nvidia-tesla-v100", max_per_instance=8, compatible_families=["n1"]),
]

REGIONS: list[RegionSpec] = [
    RegionSpec(code="us-central1", display_name="Iowa, USA"),
    RegionSpec(code="us-east1", display_name="South Carolina, USA"),
    RegionSpec(code="us-west1", display_name="Oregon, USA"),
    RegionSpec(code="europe-west1", display_name="Belgium"),
    RegionSpec(code="europe-west4", display_name="Netherlands"),
    RegionSpec(code="asia-south1", display_name="Mumbai, India"),
    RegionSpec(code="asia-southeast1", display_name="Singapore"),
]

CLOUD_SQL_TIERS: list[CloudSqlTierSpec] = [
    CloudSqlTierSpec(tier="db-f1-micro", vcpu=1, ram_gb=0.6, engines=["mysql", "postgres"]),
    CloudSqlTierSpec(tier="db-g1-small", vcpu=1, ram_gb=1.7, engines=["mysql", "postgres"]),
    CloudSqlTierSpec(tier="db-custom-2-8192", vcpu=2, ram_gb=8, engines=["mysql", "postgres", "sqlserver"]),
    CloudSqlTierSpec(tier="db-custom-4-16384", vcpu=4, ram_gb=16, engines=["mysql", "postgres", "sqlserver"]),
    CloudSqlTierSpec(tier="db-custom-8-32768", vcpu=8, ram_gb=32, engines=["mysql", "postgres", "sqlserver"]),
    CloudSqlTierSpec(tier="db-custom-16-65536", vcpu=16, ram_gb=64, engines=["mysql", "postgres", "sqlserver"]),
    CloudSqlTierSpec(tier="db-custom-32-131072", vcpu=32, ram_gb=128, engines=["mysql", "postgres", "sqlserver"]),
]

GKE_CONFIG = GkeConfig(autopilot_available=True, standard_available=True, min_node_count=1, max_node_count=1000)

VALID_REGION_CODES = {r.code for r in REGIONS}
