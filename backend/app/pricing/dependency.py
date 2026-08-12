"""Factory / DI hook for obtaining the active PricingProvider based on config."""
from functools import lru_cache

from app.core.config import get_settings
from app.pricing.base import PricingProvider
from app.pricing.mock_provider import MockGCPPricingProvider


@lru_cache
def get_pricing_provider() -> PricingProvider:
    settings = get_settings()

    if settings.cloud_provider == "aws":
        from app.pricing.aws_provider import AwsPricingProvider
        return AwsPricingProvider()

    if settings.cloud_provider == "azure":
        from app.pricing.azure_provider import AzurePricingProvider
        return AzurePricingProvider()

    # cloud_provider == "gcp": preserve the existing mock/live toggle exactly.
    if settings.pricing_provider == "gcp":
        from app.pricing.cache import get_sku_cache
        from app.pricing.gcp_provider import GcpPricingProvider

        return GcpPricingProvider.from_settings(settings, get_sku_cache())
    return MockGCPPricingProvider()
