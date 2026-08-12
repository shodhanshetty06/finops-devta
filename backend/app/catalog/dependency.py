"""Factory / DI hook for obtaining the active CatalogProvider based on config."""
from functools import lru_cache

from app.catalog.base import CatalogProvider
from app.catalog.mock_provider import MockCatalogProvider
from app.core.config import get_settings


@lru_cache
def get_catalog_provider() -> CatalogProvider:
    settings = get_settings()

    if settings.cloud_provider == "aws":
        from app.catalog.aws_provider import AwsCatalogProvider
        return AwsCatalogProvider()

    if settings.cloud_provider == "azure":
        from app.catalog.azure_provider import AzureCatalogProvider
        return AzureCatalogProvider()

    # cloud_provider == "gcp": no live GcpCatalogProvider has been built (see
    # docs/ROADMAP.md Phase 5) - the mock catalog already mirrors GCP's real
    # supported-value sets closely enough for validation purposes, regardless
    # of whether *pricing* is mock or live (FINOPS_PRICING_PROVIDER). Bug fix
    # (Phase 9): this used to gate on pricing_provider=="gcp" and raise
    # NotImplementedError in that case, which meant enabling live GCP pricing
    # broke catalog resolution entirely - the two settings were never
    # supposed to be coupled.
    return MockCatalogProvider()
