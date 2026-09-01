"""Catalog entry models - the shape of a "supported configuration" regardless
of whether it was fetched from the live Google Cloud APIs or a mock dataset."""
from pydantic import BaseModel


class MachineTypeSpec(BaseModel):
    name: str            # e.g. "e2-standard-4"
    family: str           # e.g. "e2"
    vcpu: int
    ram_gb: float
    supports_gpu: bool = False


class MachineFamilyCapability(BaseModel):
    """What a Compute Engine machine family supports, for validating a
    request BEFORE it reaches pricing (see app/validation/rules.py's
    CustomMachineTypeValidationRule / MachineFamilyRegionValidationRule) -
    never assume every family accepts an arbitrary custom vCPU/RAM shape or
    is available in every region.

    Ranges/increments below approximate Google's publicly documented custom
    machine type rules; this sandbox has no network path to Google (same
    constraint noted in app/pricing/sku_matcher.py's module docstring), so
    treat these as a reasonable default, not a verified live-catalog fact -
    re-verify against the Compute Engine API/docs before production use.

    `available_regions`: Google's real ground truth for "is this machine
    type launched in this exact region" is the Compute Engine Machine Types
    API (`machineTypes.list` per zone) - this project has no integration
    with that API. The Cloud Billing Catalog SKUs this project's pricing
    layer already fetches are a poor substitute for that specific question:
    Google groups many SKUs' `serviceRegions` by broad geography (see the
    "running in Americas" / "running in EMEA" fixtures throughout
    app/pricing/sku_matcher.py and its tests), which answers "is this family
    billable/priced in this region" but not "is this exact machine type
    actually orderable there" - a newly-launched family can be priced
    catalog-wide before it's available everywhere. So `available_regions`
    here is deliberately a *small, explicit list of known exceptions* for
    families with genuinely limited rollout (kept intentionally short, not
    a large hand-maintained matrix) - `None` means "available in every
    region this catalog supports" and is left as the default for every
    well-established family."""

    family: str
    supports_predefined: bool = True
    supports_custom: bool = False
    min_vcpu: int | None = None
    max_vcpu: int | None = None
    vcpu_step: int = 1               # allowed vCPU increment for custom shapes (e.g. N2 requires even counts)
    min_ram_gb_per_vcpu: float | None = None
    max_ram_gb_per_vcpu: float | None = None
    ram_increment_gb: float = 0.25   # Google's custom RAM must be a multiple of 256 MB
    available_regions: list[str] | None = None


class DiskTypeSpec(BaseModel):
    name: str            # e.g. "pd-ssd"
    min_size_gb: int
    max_size_gb: int
    description: str


class GpuSpec(BaseModel):
    name: str
    max_per_instance: int
    compatible_families: list[str]


class RegionSpec(BaseModel):
    code: str            # e.g. "us-central1"
    display_name: str
    multi_zone: bool = True


class CloudSqlTierSpec(BaseModel):
    tier: str             # e.g. "db-custom-2-8192"
    vcpu: int
    ram_gb: float
    engines: list[str]


class GkeConfig(BaseModel):
    autopilot_available: bool = True
    standard_available: bool = True
    min_node_count: int = 1
    max_node_count: int = 1000
