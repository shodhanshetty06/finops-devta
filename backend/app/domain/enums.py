"""Shared enumerations used across domain models."""
import re
from enum import Enum


class Severity(str, Enum):
    """Severity of a validation finding."""

    INFO = "info"          # informational only, no action needed
    WARNING = "warning"    # value was adjusted, estimate proceeds
    BLOCKER = "blocker"    # request cannot be satisfied even after normalization


class MachineFamily(str, Enum):
    E2 = "e2"
    N1 = "n1"
    N2 = "n2"
    N2D = "n2d"
    N4 = "n4"
    N4D = "n4d"
    N4A = "n4a"   # Arm (Axion)
    C2 = "c2"
    C3 = "c3"
    C3D = "c3d"
    C4 = "c4"
    C4D = "c4d"
    C4A = "c4a"   # Arm (Axion)
    T2D = "t2d"
    T2A = "t2a"   # Arm
    A2 = "a2"     # GPU-optimized


def normalize_token(raw: str) -> str:
    """Collapses case/whitespace/hyphen/underscore variance so "N2D",
    "n2d", "N2-D", and "n2 d" all compare equal - used for matching a
    free-form field/enum string against a canonical value, never for
    substring/prefix matching (that would let "n2" incorrectly match input
    meant for "n2d" - see MachineFamily's own values, several of which are
    prefixes of one another). Shared by every enum-valued FieldSpec in
    app/intake/build.py::coerce_value, not just MachineFamily."""
    return re.sub(r"[\s_-]+", "", raw.strip().lower())


def resolve_machine_family(raw: str) -> "MachineFamily | None":
    """Resolves a free-form machine family string (any case/separator
    variant) to its canonical MachineFamily member, or None if it matches
    none. Exact match only, after normalization - never a substring/prefix
    match, which would risk resolving "n2d" input to MachineFamily.N2."""
    norm = normalize_token(raw)
    for member in MachineFamily:
        if normalize_token(member.value) == norm:
            return member
    return None


class MachineTypeKind(str, Enum):
    """Whether a ComputeRequirement's vCPU/RAM should be resolved to a named
    predefined machine type (e.g. "n2d-standard-4") or priced exactly as
    the custom vCPU/RAM shape requested. Optional on ComputeRequirement -
    omitted (None) preserves this platform's historical behavior (resolve
    to the nearest predefined type, see NormalizationEngine._normalize_compute)."""

    PREDEFINED = "predefined"
    CUSTOM = "custom"


class Region(str, Enum):
    US_CENTRAL1 = "us-central1"
    US_EAST1 = "us-east1"
    US_WEST1 = "us-west1"
    EUROPE_WEST1 = "europe-west1"
    EUROPE_WEST4 = "europe-west4"
    ASIA_SOUTH1 = "asia-south1"
    ASIA_SOUTHEAST1 = "asia-southeast1"


class DiskType(str, Enum):
    PD_STANDARD = "pd-standard"
    PD_BALANCED = "pd-balanced"
    PD_SSD = "pd-ssd"
    PD_EXTREME = "pd-extreme"


class GpuType(str, Enum):
    NONE = "none"
    NVIDIA_T4 = "nvidia-tesla-t4"
    NVIDIA_L4 = "nvidia-l4"
    NVIDIA_A100_40GB = "nvidia-tesla-a100"
    NVIDIA_V100 = "nvidia-tesla-v100"


class ProvisioningModel(str, Enum):
    """On-demand vs. Spot (preemptible) VM pricing. Committed Use Discounts
    are a separate axis, selected via the `commitment_term_years` parameter
    on `POST /api/v1/estimate` (see app/api/routers/estimate.py) rather than
    here, since a commitment is a billing-account-level purchase, not a
    per-instance property, and already has its own tested pipeline
    (PricingEngine, CommitmentEngine). A Spot instance is never eligible for
    a Committed Use Discount on real Google Cloud, so PricingEngine treats
    the two as mutually exclusive - Spot wins if both are somehow supplied."""

    ON_DEMAND = "on_demand"
    SPOT = "spot"


class OperatingSystem(str, Enum):
    """The guest OS/license running on a Compute Engine instance. Free Linux
    distributions (Debian, Ubuntu, CentOS, Rocky, etc.) carry no separate
    licensing SKU on Google Cloud, so LINUX has no cost impact; the others
    add a per-vCPU or flat per-instance licensing surcharge on top of the
    infrastructure price (see app/pricing/mock_data.py)."""

    LINUX = "linux"
    WINDOWS_SERVER = "windows_server"
    RHEL = "rhel"
    SUSE = "suse"


class GkeEdition(str, Enum):
    """GKE Standard edition vs. Enterprise edition (adds fleet-wide policy/
    security/multi-cluster management features for a per-vCPU/hour
    surcharge on top of the regular cluster management fee)."""

    STANDARD = "standard"
    ENTERPRISE = "enterprise"


class CloudSqlEngine(str, Enum):
    POSTGRES = "postgres"
    MYSQL = "mysql"
    SQLSERVER = "sqlserver"


class BackupFrequency(str, Enum):
    NONE = "none"
    DAILY = "daily"
    HOURLY = "hourly"


class WorkloadTier(str, Enum):
    """Used by the AI recommendation engine when only business needs are given."""

    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"
