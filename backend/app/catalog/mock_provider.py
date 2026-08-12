"""In-memory CatalogProvider backed by `mock_data`. Deterministic and
dependency-free, so it works offline and in unit tests. Swap for
`GcpCatalogProvider` in production once GCP credentials are available."""
from app.catalog import mock_data
from app.catalog.base import CatalogProvider
from app.catalog.models import (
    CloudSqlTierSpec,
    DiskTypeSpec,
    GkeConfig,
    GpuSpec,
    MachineTypeSpec,
    RegionSpec,
)


class MockCatalogProvider(CatalogProvider):
    def list_machine_types(self, family: str | None = None) -> list[MachineTypeSpec]:
        if family is None:
            return list(mock_data.MACHINE_TYPES)
        return [m for m in mock_data.MACHINE_TYPES if m.family == family]

    def list_disk_types(self) -> list[DiskTypeSpec]:
        return list(mock_data.DISK_TYPES)

    def list_gpu_types(self) -> list[GpuSpec]:
        return list(mock_data.GPU_TYPES)

    def list_regions(self) -> list[RegionSpec]:
        return list(mock_data.REGIONS)

    def list_cloud_sql_tiers(self, engine: str | None = None) -> list[CloudSqlTierSpec]:
        tiers = mock_data.CLOUD_SQL_TIERS
        if engine is None:
            return list(tiers)
        return [t for t in tiers if engine in t.engines]

    def get_gke_config(self) -> GkeConfig:
        return mock_data.GKE_CONFIG

    def is_region_supported(self, region_code: str) -> bool:
        return region_code in mock_data.VALID_REGION_CODES
