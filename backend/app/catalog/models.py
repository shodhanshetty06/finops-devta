"""Catalog entry models - the shape of a "supported configuration" regardless
of whether it was fetched from the live Google Cloud APIs or a mock dataset."""
from pydantic import BaseModel


class MachineTypeSpec(BaseModel):
    name: str            # e.g. "e2-standard-4"
    family: str           # e.g. "e2"
    vcpu: int
    ram_gb: float
    supports_gpu: bool = False


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
