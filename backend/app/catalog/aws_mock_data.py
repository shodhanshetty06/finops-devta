"""
Static reference data describing valid AWS configurations, mapped onto this
platform's cloud-agnostic canonical vocabulary (see `app/catalog/aws_provider.py`
for the mapping rationale). Real AWS instance/tier names and specs (vCPU/RAM),
approximate as of early 2026 - for demo/comparison purposes, not real invoicing.
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
# values) so `list_machine_types(family=...)` keeps working unmodified for
# every cloud; `name` carries the real AWS EC2 instance type.
MACHINE_TYPES: list[MachineTypeSpec] = [
    # e2 (canonical: cost-optimized/burstable) -> EC2 T3 (burstable, general purpose)
    MachineTypeSpec(name="t3.nano", family="e2", vcpu=2, ram_gb=0.5),
    MachineTypeSpec(name="t3.micro", family="e2", vcpu=2, ram_gb=1),
    MachineTypeSpec(name="t3.small", family="e2", vcpu=2, ram_gb=2),
    MachineTypeSpec(name="t3.medium", family="e2", vcpu=2, ram_gb=4),
    MachineTypeSpec(name="t3.large", family="e2", vcpu=2, ram_gb=8),
    MachineTypeSpec(name="t3.xlarge", family="e2", vcpu=4, ram_gb=16),
    MachineTypeSpec(name="t3.2xlarge", family="e2", vcpu=8, ram_gb=32),
    # n2 (canonical: balanced general purpose) -> EC2 M5
    MachineTypeSpec(name="m5.large", family="n2", vcpu=2, ram_gb=8),
    MachineTypeSpec(name="m5.xlarge", family="n2", vcpu=4, ram_gb=16),
    MachineTypeSpec(name="m5.2xlarge", family="n2", vcpu=8, ram_gb=32),
    MachineTypeSpec(name="m5.4xlarge", family="n2", vcpu=16, ram_gb=64),
    MachineTypeSpec(name="m5.8xlarge", family="n2", vcpu=32, ram_gb=128),
    MachineTypeSpec(name="m5.12xlarge", family="n2", vcpu=48, ram_gb=192),
    MachineTypeSpec(name="m5.16xlarge", family="n2", vcpu=64, ram_gb=256),
    # n2d (canonical: AMD-based, cost-optimized) -> EC2 M6a
    MachineTypeSpec(name="m6a.large", family="n2d", vcpu=2, ram_gb=8),
    MachineTypeSpec(name="m6a.xlarge", family="n2d", vcpu=4, ram_gb=16),
    MachineTypeSpec(name="m6a.2xlarge", family="n2d", vcpu=8, ram_gb=32),
    MachineTypeSpec(name="m6a.4xlarge", family="n2d", vcpu=16, ram_gb=64),
    # c2 (canonical: compute-optimized) -> EC2 C5
    MachineTypeSpec(name="c5.xlarge", family="c2", vcpu=4, ram_gb=8),
    MachineTypeSpec(name="c5.2xlarge", family="c2", vcpu=8, ram_gb=16),
    MachineTypeSpec(name="c5.4xlarge", family="c2", vcpu=16, ram_gb=32),
    MachineTypeSpec(name="c5.9xlarge", family="c2", vcpu=36, ram_gb=72),
    MachineTypeSpec(name="c5.18xlarge", family="c2", vcpu=72, ram_gb=144),
    # a2 (canonical: GPU-optimized) -> EC2 G4dn/P3/P4d
    MachineTypeSpec(name="g4dn.xlarge", family="a2", vcpu=4, ram_gb=16, supports_gpu=True),
    MachineTypeSpec(name="p3.8xlarge", family="a2", vcpu=32, ram_gb=244, supports_gpu=True),
    MachineTypeSpec(name="p4d.24xlarge", family="a2", vcpu=96, ram_gb=1152, supports_gpu=True),
]

# `name` must stay the canonical DiskType code (it's used as a dict lookup key
# in NormalizationEngine._normalize_storage) - the real EBS volume type is
# recorded in `description` instead, same pattern GCP's mock data would use
# if it needed to distinguish a canonical code from a display name.
DISK_TYPES: list[DiskTypeSpec] = [
    DiskTypeSpec(name="pd-standard", min_size_gb=10, max_size_gb=65536, description="EBS st1 - Throughput Optimized HDD"),
    DiskTypeSpec(name="pd-balanced", min_size_gb=10, max_size_gb=65536, description="EBS gp3 - General Purpose SSD"),
    DiskTypeSpec(name="pd-ssd", min_size_gb=10, max_size_gb=65536, description="EBS io1 - Provisioned IOPS SSD"),
    DiskTypeSpec(name="pd-extreme", min_size_gb=500, max_size_gb=65536, description="EBS io2 Block Express - highest-performance provisioned IOPS SSD"),
]

# GPU chip names are NVIDIA identifiers, not cloud-specific - they carry over
# verbatim from the GCP catalog. `compatible_families` uses the canonical a2
# GPU-optimized family tag (the only GPU-capable value in `MachineFamily`).
GPU_TYPES: list[GpuSpec] = [
    GpuSpec(name="nvidia-tesla-t4", max_per_instance=4, compatible_families=["a2"]),
    GpuSpec(name="nvidia-l4", max_per_instance=8, compatible_families=["a2"]),
    GpuSpec(name="nvidia-tesla-a100", max_per_instance=8, compatible_families=["a2"]),
    GpuSpec(name="nvidia-tesla-v100", max_per_instance=4, compatible_families=["a2"]),
]

# `code` stays the canonical Region code (also what flows through pricing) -
# `display_name` documents the real AWS region it represents.
REGIONS: list[RegionSpec] = [
    RegionSpec(code="us-central1", display_name="AWS us-east-2 (Ohio)"),
    RegionSpec(code="us-east1", display_name="AWS us-east-1 (N. Virginia)"),
    RegionSpec(code="us-west1", display_name="AWS us-west-2 (Oregon)"),
    RegionSpec(code="europe-west1", display_name="AWS eu-west-1 (Ireland)"),
    RegionSpec(code="europe-west4", display_name="AWS eu-central-1 (Frankfurt)"),
    RegionSpec(code="asia-south1", display_name="AWS ap-south-1 (Mumbai)"),
    RegionSpec(code="asia-southeast1", display_name="AWS ap-southeast-1 (Singapore)"),
]

# RDS instance tiers (M5 family, matching the compute-side M5 specs above).
CLOUD_SQL_TIERS: list[CloudSqlTierSpec] = [
    CloudSqlTierSpec(tier="db.t3.micro", vcpu=2, ram_gb=1, engines=["mysql", "postgres"]),
    CloudSqlTierSpec(tier="db.m5.large", vcpu=2, ram_gb=8, engines=["mysql", "postgres", "sqlserver"]),
    CloudSqlTierSpec(tier="db.m5.xlarge", vcpu=4, ram_gb=16, engines=["mysql", "postgres", "sqlserver"]),
    CloudSqlTierSpec(tier="db.m5.2xlarge", vcpu=8, ram_gb=32, engines=["mysql", "postgres", "sqlserver"]),
    CloudSqlTierSpec(tier="db.m5.4xlarge", vcpu=16, ram_gb=64, engines=["mysql", "postgres", "sqlserver"]),
    CloudSqlTierSpec(tier="db.m5.8xlarge", vcpu=32, ram_gb=128, engines=["mysql", "postgres", "sqlserver"]),
]

# EKS: Fargate (serverless nodes) is the closest analogue to GKE Autopilot;
# standard managed node groups are the closest analogue to GKE Standard.
GKE_CONFIG = GkeConfig(autopilot_available=True, standard_available=True, min_node_count=1, max_node_count=1000)

VALID_REGION_CODES = {r.code for r in REGIONS}
