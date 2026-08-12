"""
Static reference data describing valid Azure configurations, mapped onto
this platform's cloud-agnostic canonical vocabulary (see
`app/catalog/azure_provider.py` for the mapping rationale). Real Azure VM
size/tier names and specs (vCPU/RAM), approximate as of early 2026 - for
demo/comparison purposes, not real invoicing.
"""
from app.catalog.models import (
    CloudSqlTierSpec,
    DiskTypeSpec,
    GkeConfig,
    GpuSpec,
    MachineTypeSpec,
    RegionSpec,
)

# `family` is the canonical compute-tier code (matches `MachineFamily` enum
# values); `name` carries the real Azure VM size.
MACHINE_TYPES: list[MachineTypeSpec] = [
    # e2 (canonical: cost-optimized/burstable) -> Bsv2-series (burstable)
    MachineTypeSpec(name="Standard_B1s", family="e2", vcpu=1, ram_gb=1),
    MachineTypeSpec(name="Standard_B1ms", family="e2", vcpu=1, ram_gb=2),
    MachineTypeSpec(name="Standard_B2s", family="e2", vcpu=2, ram_gb=4),
    MachineTypeSpec(name="Standard_B2ms", family="e2", vcpu=2, ram_gb=8),
    MachineTypeSpec(name="Standard_B4ms", family="e2", vcpu=4, ram_gb=16),
    MachineTypeSpec(name="Standard_B8ms", family="e2", vcpu=8, ram_gb=32),
    MachineTypeSpec(name="Standard_B16ms", family="e2", vcpu=16, ram_gb=64),
    # n2 (canonical: balanced general purpose) -> Dsv5-series
    MachineTypeSpec(name="Standard_D2s_v5", family="n2", vcpu=2, ram_gb=8),
    MachineTypeSpec(name="Standard_D4s_v5", family="n2", vcpu=4, ram_gb=16),
    MachineTypeSpec(name="Standard_D8s_v5", family="n2", vcpu=8, ram_gb=32),
    MachineTypeSpec(name="Standard_D16s_v5", family="n2", vcpu=16, ram_gb=64),
    MachineTypeSpec(name="Standard_D32s_v5", family="n2", vcpu=32, ram_gb=128),
    MachineTypeSpec(name="Standard_D48s_v5", family="n2", vcpu=48, ram_gb=192),
    MachineTypeSpec(name="Standard_D64s_v5", family="n2", vcpu=64, ram_gb=256),
    # n2d (canonical: AMD-based, cost-optimized) -> Dasv5-series
    MachineTypeSpec(name="Standard_D2as_v5", family="n2d", vcpu=2, ram_gb=8),
    MachineTypeSpec(name="Standard_D4as_v5", family="n2d", vcpu=4, ram_gb=16),
    MachineTypeSpec(name="Standard_D8as_v5", family="n2d", vcpu=8, ram_gb=32),
    MachineTypeSpec(name="Standard_D16as_v5", family="n2d", vcpu=16, ram_gb=64),
    # c2 (canonical: compute-optimized) -> Fsv2-series
    MachineTypeSpec(name="Standard_F4s_v2", family="c2", vcpu=4, ram_gb=8),
    MachineTypeSpec(name="Standard_F8s_v2", family="c2", vcpu=8, ram_gb=16),
    MachineTypeSpec(name="Standard_F16s_v2", family="c2", vcpu=16, ram_gb=32),
    MachineTypeSpec(name="Standard_F32s_v2", family="c2", vcpu=32, ram_gb=64),
    MachineTypeSpec(name="Standard_F72s_v2", family="c2", vcpu=72, ram_gb=144),
    # a2 (canonical: GPU-optimized) -> NC-series
    MachineTypeSpec(name="Standard_NC4as_T4_v3", family="a2", vcpu=4, ram_gb=28, supports_gpu=True),
    MachineTypeSpec(name="Standard_NC24s_v3", family="a2", vcpu=24, ram_gb=448, supports_gpu=True),
    MachineTypeSpec(name="Standard_ND96asr_v4", family="a2", vcpu=96, ram_gb=900, supports_gpu=True),
]

# `name` must stay the canonical DiskType code (used as a dict lookup key in
# NormalizationEngine._normalize_storage); the real Azure Managed Disk tier
# is recorded in `description`.
DISK_TYPES: list[DiskTypeSpec] = [
    DiskTypeSpec(name="pd-standard", min_size_gb=10, max_size_gb=65536, description="Standard HDD managed disk"),
    DiskTypeSpec(name="pd-balanced", min_size_gb=10, max_size_gb=65536, description="Standard SSD managed disk"),
    DiskTypeSpec(name="pd-ssd", min_size_gb=10, max_size_gb=65536, description="Premium SSD managed disk"),
    DiskTypeSpec(name="pd-extreme", min_size_gb=500, max_size_gb=65536, description="Ultra Disk - provisioned IOPS/throughput"),
]

# GPU chip names are NVIDIA identifiers, not cloud-specific - carried over
# verbatim from the GCP catalog. `compatible_families` uses the canonical a2
# GPU-optimized family tag (the only GPU-capable value in `MachineFamily`).
GPU_TYPES: list[GpuSpec] = [
    GpuSpec(name="nvidia-tesla-t4", max_per_instance=4, compatible_families=["a2"]),
    GpuSpec(name="nvidia-l4", max_per_instance=8, compatible_families=["a2"]),
    GpuSpec(name="nvidia-tesla-a100", max_per_instance=8, compatible_families=["a2"]),
    GpuSpec(name="nvidia-tesla-v100", max_per_instance=4, compatible_families=["a2"]),
]

# `code` stays the canonical Region code (also what flows through pricing) -
# `display_name` documents the real Azure region it represents.
REGIONS: list[RegionSpec] = [
    RegionSpec(code="us-central1", display_name="Azure Central US"),
    RegionSpec(code="us-east1", display_name="Azure East US"),
    RegionSpec(code="us-west1", display_name="Azure West US 2"),
    RegionSpec(code="europe-west1", display_name="Azure West Europe"),
    RegionSpec(code="europe-west4", display_name="Azure Germany West Central"),
    RegionSpec(code="asia-south1", display_name="Azure Central India"),
    RegionSpec(code="asia-southeast1", display_name="Azure Southeast Asia"),
]

# Azure Database for MySQL/PostgreSQL / Azure SQL Database General Purpose
# Gen5 vCore tiers (RAM simplified to round numbers for readability).
CLOUD_SQL_TIERS: list[CloudSqlTierSpec] = [
    CloudSqlTierSpec(tier="Standard_B1ms (DB)", vcpu=1, ram_gb=2, engines=["mysql", "postgres"]),
    CloudSqlTierSpec(tier="GP_Gen5_2", vcpu=2, ram_gb=10, engines=["mysql", "postgres", "sqlserver"]),
    CloudSqlTierSpec(tier="GP_Gen5_4", vcpu=4, ram_gb=20, engines=["mysql", "postgres", "sqlserver"]),
    CloudSqlTierSpec(tier="GP_Gen5_8", vcpu=8, ram_gb=40, engines=["mysql", "postgres", "sqlserver"]),
    CloudSqlTierSpec(tier="GP_Gen5_16", vcpu=16, ram_gb=80, engines=["mysql", "postgres", "sqlserver"]),
    CloudSqlTierSpec(tier="GP_Gen5_32", vcpu=32, ram_gb=160, engines=["mysql", "postgres", "sqlserver"]),
]

# AKS: virtual nodes (serverless, ACI-backed) are the closest analogue to GKE
# Autopilot; standard AKS node pools are the closest analogue to GKE Standard.
GKE_CONFIG = GkeConfig(autopilot_available=True, standard_available=True, min_node_count=1, max_node_count=1000)

VALID_REGION_CODES = {r.code for r in REGIONS}
