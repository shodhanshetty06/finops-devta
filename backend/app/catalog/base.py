"""CatalogProvider interface. All validation/normalization code depends on
this abstraction, never on a concrete data source - so a future
`GcpCatalogProvider` backed by the live Compute Engine / Cloud SQL Admin APIs
can be swapped in via dependency injection without touching business logic."""
from abc import ABC, abstractmethod

from app.catalog.models import (
    CloudSqlTierSpec,
    DiskTypeSpec,
    GkeConfig,
    GpuSpec,
    MachineTypeSpec,
    RegionSpec,
)


class CatalogProvider(ABC):
    @abstractmethod
    def list_machine_types(self, family: str | None = None) -> list[MachineTypeSpec]: ...

    @abstractmethod
    def list_disk_types(self) -> list[DiskTypeSpec]: ...

    @abstractmethod
    def list_gpu_types(self) -> list[GpuSpec]: ...

    @abstractmethod
    def list_regions(self) -> list[RegionSpec]: ...

    @abstractmethod
    def list_cloud_sql_tiers(self, engine: str | None = None) -> list[CloudSqlTierSpec]: ...

    @abstractmethod
    def get_gke_config(self) -> GkeConfig: ...

    @abstractmethod
    def is_region_supported(self, region_code: str) -> bool: ...
