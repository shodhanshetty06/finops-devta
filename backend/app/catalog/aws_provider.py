"""
AwsCatalogProvider: implements the exact same `CatalogProvider` interface
`MockCatalogProvider`/a future `GcpCatalogProvider` do (Phase 9 - multi-cloud
extensibility). No live AWS API integration is built this phase (Pricing/
Service Quotas APIs would be the equivalent of Phase 5's live GCP work) -
this is a mock provider, same status as `MockCatalogProvider` for GCP.

Cloud-agnostic vocabulary: `Region` and `MachineFamily` enum values (defined
once, GCP-shaped, in `app/domain/enums.py`) are treated as canonical codes
here, not literal AWS identifiers - e.g. requesting region "us-central1" or
family "e2" against this provider resolves to AWS's real us-east-2 region
and T3 instance family respectively (see `aws_mock_data.py` for the full
mapping). This lets `CustomerRequirement`, the validation engine, and the
normalization engine work completely unmodified regardless of which cloud
is active - only the catalog/pricing provider changes what a given
canonical code *means*.
"""
from app.catalog import aws_mock_data
from app.catalog.base import CatalogProvider
from app.catalog.models import (
    CloudSqlTierSpec,
    DiskTypeSpec,
    GkeConfig,
    GpuSpec,
    MachineFamilyCapability,
    MachineTypeSpec,
    RegionSpec,
)


class AwsCatalogProvider(CatalogProvider):
    def list_machine_types(self, family: str | None = None) -> list[MachineTypeSpec]:
        if family is None:
            return list(aws_mock_data.MACHINE_TYPES)
        return [m for m in aws_mock_data.MACHINE_TYPES if m.family == family]

    def get_machine_type(self, name: str) -> MachineTypeSpec | None:
        return next((m for m in aws_mock_data.MACHINE_TYPES if m.name == name), None)

    def list_family_capabilities(self) -> list[MachineFamilyCapability]:
        # AWS EC2 has no equivalent of a GCP "custom machine type" - every
        # family here is fixed predefined instance sizes only.
        families = {m.family for m in aws_mock_data.MACHINE_TYPES}
        return [MachineFamilyCapability(family=f, supports_custom=False) for f in sorted(families)]

    def get_family_capability(self, family: str) -> MachineFamilyCapability | None:
        return next((c for c in self.list_family_capabilities() if c.family == family), None)

    def list_disk_types(self) -> list[DiskTypeSpec]:
        return list(aws_mock_data.DISK_TYPES)

    def list_gpu_types(self) -> list[GpuSpec]:
        return list(aws_mock_data.GPU_TYPES)

    def list_regions(self) -> list[RegionSpec]:
        return list(aws_mock_data.REGIONS)

    def list_cloud_sql_tiers(self, engine: str | None = None) -> list[CloudSqlTierSpec]:
        tiers = aws_mock_data.CLOUD_SQL_TIERS
        if engine is None:
            return list(tiers)
        return [t for t in tiers if engine in t.engines]

    def get_gke_config(self) -> GkeConfig:
        return aws_mock_data.GKE_CONFIG

    def is_region_supported(self, region_code: str) -> bool:
        return region_code in aws_mock_data.VALID_REGION_CODES
