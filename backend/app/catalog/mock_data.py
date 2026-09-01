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
    MachineFamilyCapability,
    MachineTypeSpec,
    RegionSpec,
)


def _standard_family(prefix: str, family: str, vcpus: list[int], gb_per_vcpu: float) -> list[MachineTypeSpec]:
    """Generates a "<prefix>-standard-<n>" progression at a fixed GB/vCPU
    ratio - the shape every general-purpose GCP family's standard tier
    follows. Kept as a helper (rather than repeating each MachineTypeSpec by
    hand) so a new family/size can be added as one line instead of N."""
    return [MachineTypeSpec(name=f"{prefix}-standard-{v}", family=family, vcpu=v, ram_gb=v * gb_per_vcpu) for v in vcpus]


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
    # N1 - first-generation general purpose, 3.75 GB/vCPU
    *_standard_family("n1", "n1", [1, 2, 4, 8, 16, 32, 64, 96], 3.75),
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
    # N4 - current-generation general purpose (standard/highmem/highcpu tiers)
    *_standard_family("n4", "n4", [2, 4, 8, 16, 32, 48, 64, 80], 4),
    *[MachineTypeSpec(name=f"n4-highmem-{v}", family="n4", vcpu=v, ram_gb=v * 8) for v in (2, 4, 8, 16, 32, 48, 64, 80)],
    *[MachineTypeSpec(name=f"n4-highcpu-{v}", family="n4", vcpu=v, ram_gb=v * 2) for v in (2, 4, 8, 16, 32, 48, 64, 80)],
    # N4D - AMD variant of N4, same shape/ratios
    *_standard_family("n4d", "n4d", [2, 4, 8, 16, 32, 48, 64, 80], 4),
    # N4A - Arm (Axion); no custom machine type support (see MACHINE_FAMILY_CAPABILITIES)
    *_standard_family("n4a", "n4a", [2, 4, 8, 16, 32, 48, 64, 80], 4),
    # C2 - compute-optimized, fixed sizes only
    MachineTypeSpec(name="c2-standard-4", family="c2", vcpu=4, ram_gb=16),
    MachineTypeSpec(name="c2-standard-8", family="c2", vcpu=8, ram_gb=32),
    MachineTypeSpec(name="c2-standard-16", family="c2", vcpu=16, ram_gb=64),
    MachineTypeSpec(name="c2-standard-30", family="c2", vcpu=30, ram_gb=120),
    MachineTypeSpec(name="c2-standard-60", family="c2", vcpu=60, ram_gb=240),
    # C3 - current-generation compute-optimized
    *_standard_family("c3", "c3", [4, 8, 22, 44, 88, 176], 4),
    # C3D - AMD variant of C3
    *_standard_family("c3d", "c3d", [4, 8, 16, 30, 60, 90, 180], 4),
    # C4 - newest-generation compute-optimized
    *_standard_family("c4", "c4", [2, 4, 8, 16, 32, 48, 96, 144], 4),
    # C4D - AMD variant of C4
    *_standard_family("c4d", "c4d", [2, 4, 8, 16, 32, 48, 96, 144], 4),
    # C4A - Arm (Axion) variant of C4; no custom machine type support
    *_standard_family("c4a", "c4a", [1, 2, 4, 8, 16, 32, 48, 72], 4),
    # T2D - AMD Tau, fixed sizes only, no custom machine type support
    *_standard_family("t2d", "t2d", [1, 2, 4, 8, 16, 32, 48, 60], 4),
    # T2A - Arm Tau, fixed sizes only, no custom machine type support
    *_standard_family("t2a", "t2a", [1, 2, 4, 8, 16, 24, 32, 48], 4),
    # A2 - GPU-optimized (paired with A100 GPUs)
    MachineTypeSpec(name="a2-highgpu-1g", family="a2", vcpu=12, ram_gb=85, supports_gpu=True),
    MachineTypeSpec(name="a2-highgpu-2g", family="a2", vcpu=24, ram_gb=170, supports_gpu=True),
    MachineTypeSpec(name="a2-highgpu-4g", family="a2", vcpu=48, ram_gb=340, supports_gpu=True),
]

# What each family supports, for validating a request BEFORE pricing (see
# app/validation/rules.py::CustomMachineTypeValidationRule). Ranges/increments
# are a documented approximation of Google's publicly published custom
# machine type rules - see MachineFamilyCapability's own docstring. This list
# is deliberately not exhaustive of every real GCP nuance (e.g. N1's "1 or
# even 2-96" vCPU rule is approximated as "any count >=1, step 2 above 2");
# extend it here as better data becomes available, never by adding a
# separate pricing implementation per family (pricing stays the single
# generic vCPU-price x vcpu + RAM-price x ram_gb formula for every family).
MACHINE_FAMILY_CAPABILITIES: list[MachineFamilyCapability] = [
    MachineFamilyCapability(family="e2", supports_custom=True, min_vcpu=2, max_vcpu=32, vcpu_step=2, min_ram_gb_per_vcpu=0.5, max_ram_gb_per_vcpu=8),
    MachineFamilyCapability(family="n1", supports_custom=True, min_vcpu=1, max_vcpu=96, vcpu_step=2, min_ram_gb_per_vcpu=0.9, max_ram_gb_per_vcpu=6.5),
    MachineFamilyCapability(family="n2", supports_custom=True, min_vcpu=2, max_vcpu=128, vcpu_step=2, min_ram_gb_per_vcpu=0.5, max_ram_gb_per_vcpu=8),
    MachineFamilyCapability(family="n2d", supports_custom=True, min_vcpu=2, max_vcpu=224, vcpu_step=2, min_ram_gb_per_vcpu=0.5, max_ram_gb_per_vcpu=8),
    MachineFamilyCapability(family="n4", supports_custom=True, min_vcpu=2, max_vcpu=80, vcpu_step=2, min_ram_gb_per_vcpu=2, max_ram_gb_per_vcpu=8),
    MachineFamilyCapability(family="n4d", supports_custom=True, min_vcpu=2, max_vcpu=80, vcpu_step=2, min_ram_gb_per_vcpu=2, max_ram_gb_per_vcpu=8),
    # n4a/c4a/t2a: the newest/Arm (Axion/Tau Arm) families - the only three
    # given an explicit `available_regions` list below (see
    # MachineFamilyCapability's docstring for why this list is kept short
    # rather than attempting a full per-family region matrix).
    MachineFamilyCapability(family="n4a", supports_custom=False, available_regions=["us-central1", "europe-west4"]),
    MachineFamilyCapability(family="c2", supports_custom=False),   # fixed sizes only
    MachineFamilyCapability(family="c3", supports_custom=True, min_vcpu=4, max_vcpu=176, vcpu_step=2, min_ram_gb_per_vcpu=2, max_ram_gb_per_vcpu=8),
    MachineFamilyCapability(family="c3d", supports_custom=True, min_vcpu=4, max_vcpu=180, vcpu_step=2, min_ram_gb_per_vcpu=2, max_ram_gb_per_vcpu=8),
    MachineFamilyCapability(family="c4", supports_custom=True, min_vcpu=2, max_vcpu=144, vcpu_step=2, min_ram_gb_per_vcpu=2, max_ram_gb_per_vcpu=8),
    MachineFamilyCapability(family="c4d", supports_custom=True, min_vcpu=2, max_vcpu=144, vcpu_step=2, min_ram_gb_per_vcpu=2, max_ram_gb_per_vcpu=8),
    MachineFamilyCapability(family="c4a", supports_custom=False, available_regions=["us-central1", "europe-west4"]),
    MachineFamilyCapability(family="t2d", supports_custom=False),  # fixed sizes only
    MachineFamilyCapability(family="t2a", supports_custom=False, available_regions=["us-central1", "europe-west4", "asia-southeast1"]),
    MachineFamilyCapability(family="a2", supports_custom=False),   # GPU-tied fixed shapes only
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
