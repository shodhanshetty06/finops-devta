"""
AzureCatalogProvider: implements the exact same `CatalogProvider` interface
`MockCatalogProvider` (GCP) and `AwsCatalogProvider` do (Phase 9 -
multi-cloud extensibility). No live Azure API integration is built this
phase - this is a mock provider, same status as `MockCatalogProvider`/
`AwsCatalogProvider`.

See `app/catalog/aws_provider.py`'s module docstring for the canonical
region/family vocabulary explanation - the same mapping approach applies
here, translated to Azure's real region/VM-size names via `azure_mock_data.py`.
"""
from app.catalog import azure_mock_data
from app.catalog.base import CatalogProvider
from app.catalog.models import (
    CloudSqlTierSpec,
    DiskTypeSpec,
    GkeConfig,
    GpuSpec,
    MachineTypeSpec,
    RegionSpec,
)


class AzureCatalogProvider(CatalogProvider):
    def list_machine_types(self, family: str | None = None) -> list[MachineTypeSpec]:
        if family is None:
            return list(azure_mock_data.MACHINE_TYPES)
        return [m for m in azure_mock_data.MACHINE_TYPES if m.family == family]

    def list_disk_types(self) -> list[DiskTypeSpec]:
        return list(azure_mock_data.DISK_TYPES)

    def list_gpu_types(self) -> list[GpuSpec]:
        return list(azure_mock_data.GPU_TYPES)

    def list_regions(self) -> list[RegionSpec]:
        return list(azure_mock_data.REGIONS)

    def list_cloud_sql_tiers(self, engine: str | None = None) -> list[CloudSqlTierSpec]:
        tiers = azure_mock_data.CLOUD_SQL_TIERS
        if engine is None:
            return list(tiers)
        return [t for t in tiers if engine in t.engines]

    def get_gke_config(self) -> GkeConfig:
        return azure_mock_data.GKE_CONFIG

    def is_region_supported(self, region_code: str) -> bool:
        return region_code in azure_mock_data.VALID_REGION_CODES
