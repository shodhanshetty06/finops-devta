"""
Cross-cloud comparison engine (Phase 9).

Always compares against each cloud's own catalog/pricing provider pair
directly - `MockCatalogProvider`+`MockGCPPricingProvider` for GCP,
`AwsCatalogProvider`+`AwsPricingProvider` for AWS,
`AzureCatalogProvider`+`AzurePricingProvider` for Azure - regardless of the
server's active `FINOPS_CLOUD_PROVIDER`/`FINOPS_PRICING_PROVIDER` settings.
This keeps a comparison run deterministic and offline (never makes a live
GCP Billing API call mid-comparison, and AWS/Azure only have mock providers
this phase anyway - see docs/ROADMAP.md Phase 9). Reuses
`EstimationService`/`PricingEngine` once per cloud, exactly like every
other comparison engine in this platform - it never computes a price
directly.
"""
from app.catalog.aws_provider import AwsCatalogProvider
from app.catalog.azure_provider import AzureCatalogProvider
from app.catalog.mock_provider import MockCatalogProvider
from app.core.config import Settings
from app.core.exceptions import FinOpsError
from app.domain.optimization import CloudComparison, CloudCostOption
from app.domain.requirements import CustomerRequirement
from app.pricing.aws_provider import AwsPricingProvider
from app.pricing.azure_provider import AzurePricingProvider
from app.pricing.mock_provider import MockGCPPricingProvider
from app.services.estimation_service import EstimationService

_PROVIDER_FACTORIES = {
    "gcp": (MockCatalogProvider, MockGCPPricingProvider),
    "aws": (AwsCatalogProvider, AwsPricingProvider),
    "azure": (AzureCatalogProvider, AzurePricingProvider),
}


class CloudComparisonEngine:
    def compare(
        self, requirement: CustomerRequirement, clouds: list[str], settings: Settings, *, force: bool = True,
    ) -> CloudComparison:
        options: list[CloudCostOption] = []
        currency = None
        for cloud in clouds:
            factory = _PROVIDER_FACTORIES.get(cloud)
            if factory is None:
                raise FinOpsError(
                    f"Unsupported cloud provider '{cloud}'. Choose one of: {sorted(_PROVIDER_FACTORIES)}.",
                    code="unsupported_cloud_provider",
                )
            catalog_cls, pricing_cls = factory
            service = EstimationService(catalog=catalog_cls(), pricing_provider=pricing_cls(), settings=settings)
            result = service.generate_estimate(requirement, force=force)
            currency = result.cost.currency
            options.append(CloudCostOption(
                cloud_provider=cloud, total_monthly=result.cost.total_monthly, currency=currency,
                primary_machine_type=result.normalized_spec.machine_type,
            ))

        if not options:
            raise FinOpsError("At least one cloud provider is required for comparison.", code="empty_comparison")

        cheapest = min(options, key=lambda o: o.total_monthly)
        most_expensive = max(options, key=lambda o: o.total_monthly)
        return CloudComparison(
            options=options,
            cheapest_cloud=cheapest.cloud_provider,
            most_expensive_cloud=most_expensive.cloud_provider,
            max_savings_monthly=round(most_expensive.total_monthly - cheapest.total_monthly, 2),
            currency=currency or "USD",
        )
