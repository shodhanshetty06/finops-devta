"""
EstimationService: top-level orchestrator implementing the full pipeline:

  1. AI recommendation (only if compute spec is missing - business-only input)
  2. Validation (rule engine against the catalog)
  3. Block on unresolved BLOCKER-severity findings (unless force=True)
  4. Normalization (strategy-driven substitution to valid GCP configurations)
  5. Architecture recommendation
  6. Pricing (always via PricingProvider, never computed ad hoc)
  7. Audit log assembly

This is the only class API routers should call for estimate generation -
callers never talk to the rule engine / normalization engine / pricing
engine directly, so the pipeline order and audit trail stay consistent.
"""
import uuid

from app.catalog.base import CatalogProvider
from app.catalog.generic_pricing import GenericServicePricingCalculator
from app.catalog.legacy_resource_summary import build_legacy_resource_summaries
from app.catalog.messaging_observability_pricing import MessagingObservabilityPricingCalculator
from app.catalog.resource_summary import build_resource_summaries
from app.catalog.service_catalog_bridge import apply_bridged_services
from app.catalog.service_definitions import SERVICE_CATALOG_BY_ID
from app.core.config import NormalizationStrategy, Settings
from app.core.exceptions import ValidationFailedError
from app.domain.architecture import ArchitectureComponent
from app.domain.estimate import EstimateResult
from app.domain.requirements import CustomerRequirement
from app.audit.logger import AuditLogger
from app.normalization.engine import NormalizationEngine
from app.pricing.base import PricingProvider
from app.pricing.engine import PricingEngine
from app.services.architecture_engine import ArchitectureEngine
from app.services.recommendation_engine import RecommendationEngine
from app.validation.engine import ValidationRuleEngine


class EstimationService:
    def __init__(
        self,
        catalog: CatalogProvider,
        pricing_provider: PricingProvider,
        settings: Settings,
        validation_engine: ValidationRuleEngine | None = None,
        normalization_engine: NormalizationEngine | None = None,
        pricing_engine: PricingEngine | None = None,
        architecture_engine: ArchitectureEngine | None = None,
        recommendation_engine: RecommendationEngine | None = None,
        generic_service_pricing_calculator: GenericServicePricingCalculator | None = None,
        messaging_observability_pricing_calculator: MessagingObservabilityPricingCalculator | None = None,
    ):
        self.catalog = catalog
        self.pricing_provider = pricing_provider
        self.settings = settings
        self.validation_engine = validation_engine or ValidationRuleEngine()
        self.normalization_engine = normalization_engine or NormalizationEngine()
        self.pricing_engine = pricing_engine or PricingEngine()
        self.architecture_engine = architecture_engine or ArchitectureEngine()
        self.recommendation_engine = recommendation_engine or RecommendationEngine()
        self.generic_service_pricing_calculator = generic_service_pricing_calculator or GenericServicePricingCalculator()
        self.messaging_observability_pricing_calculator = (
            messaging_observability_pricing_calculator or MessagingObservabilityPricingCalculator()
        )

    def generate_estimate(
        self,
        requirement: CustomerRequirement,
        *,
        force: bool = False,
        commitment_term_years: int = 0,
    ) -> EstimateResult:
        estimate_id = str(uuid.uuid4())
        audit = AuditLogger(estimate_id)

        strategy = self._resolve_strategy(requirement)
        audit.record("pipeline_start", f"Estimate requested for project '{requirement.project_name}'.",
                     strategy=strategy.value, region=requirement.region.value)

        working_requirement = requirement
        ai_assumptions = []
        if requirement.compute is None and requirement.business is not None:
            working_requirement, ai_assumptions = self.recommendation_engine.recommend(requirement)
            audit.record_assumptions(ai_assumptions, actor="ai_recommendation_engine")
            audit.record("ai_recommendation", "Compute specification was not provided; AI recommendation engine inferred infrastructure from business context.")

        # Service-catalog selections that overlap with the legacy typed
        # schema (Persistent Disk, Cloud SQL, GKE, Networking) are bridged
        # into storage/database/kubernetes/network here, BEFORE validation,
        # so they're validated/normalized/priced identically to a classic
        # /questionnaire submission via the existing engines below.
        # `generic_selections` (everything else in the catalog) is priced
        # separately, right before the pricing engine runs.
        working_requirement, generic_selections = apply_bridged_services(working_requirement)
        if requirement.selected_services:
            audit.record(
                "service_catalog",
                f"{len(requirement.selected_services)} service(s) selected from the GCP service catalog "
                f"({len(requirement.selected_services) - len(generic_selections)} bridged into existing pricing, "
                f"{len(generic_selections)} priced generically).",
            )

        validation_report = self.validation_engine.run(working_requirement, self.catalog)
        audit.record_validation(validation_report)

        if validation_report.has_blockers and not force:
            audit.record("pipeline_blocked", f"{validation_report.blocker_count} blocker(s) found; estimate generation halted.")
            raise ValidationFailedError(
                f"Request has {validation_report.blocker_count} blocking validation issue(s) that must be resolved "
                "before an estimate can be generated. Pass force=true to override and normalize anyway.",
                results=validation_report.results,
            )

        normalized_spec, normalization_assumptions = self.normalization_engine.normalize(
            working_requirement, self.catalog, strategy
        )
        audit.record_assumptions(normalization_assumptions, actor="normalization_engine")

        architecture = self.architecture_engine.generate(working_requirement, normalized_spec)
        for selection in working_requirement.selected_services:
            definition = SERVICE_CATALOG_BY_ID.get(selection.service_id)
            if definition is None:
                continue
            architecture.components.append(ArchitectureComponent(
                layer=definition.category,
                service=definition.display_name,
                rationale="Selected in the GCP service catalog.",
            ))
        audit.record("architecture_recommendation", architecture.summary)

        service_line_items, service_assumptions = self.generic_service_pricing_calculator.calculate(
            generic_selections, self.pricing_provider.get_currency(),
        )
        sku_priced_items, sku_priced_assumptions = self.messaging_observability_pricing_calculator.calculate(
            generic_selections, self.pricing_provider, working_requirement.region.value,
        )
        service_line_items = service_line_items + sku_priced_items
        service_assumptions = service_assumptions + sku_priced_assumptions

        catalog_resource_summaries = build_resource_summaries(
            generic_selections,
            self.generic_service_pricing_calculator,
            self.messaging_observability_pricing_calculator,
            self.pricing_provider,
            self.pricing_provider.get_currency(),
            working_requirement.region.value,
            assumptions=service_assumptions,
        )

        cost = self.pricing_engine.calculate(
            normalized_spec, working_requirement, self.pricing_provider, self.settings,
            commitment_term_years=commitment_term_years,
            extra_line_items=service_line_items,
        )

        # `cost.line_items` = the legacy spec/requirement-driven items
        # PricingEngine computed itself, followed by `service_line_items`
        # (extra_line_items, appended verbatim at the end - see
        # PricingEngine.calculate). Slicing off exactly that many items from
        # the tail recovers the legacy-only items with zero risk of a
        # sku_id collision with the catalog path, so build_resource_summaries
        # (catalog) and build_legacy_resource_summaries (below) can never
        # double-count or drop a line item between them.
        n_extra = len(service_line_items)
        legacy_line_items = cost.line_items[:-n_extra] if n_extra else list(cost.line_items)
        legacy_resource_summaries = build_legacy_resource_summaries(
            legacy_line_items, normalized_spec, working_requirement,
            normalization_assumptions, validation_report,
        )

        resource_summaries = legacy_resource_summaries + catalog_resource_summaries
        category_totals: dict[str, float] = {}
        for r in resource_summaries:
            if r.category is None:
                continue
            category_totals[r.category] = round(category_totals.get(r.category, 0.0) + r.subtotal, 2)

        cost = cost.model_copy(update={
            "resource_summaries": resource_summaries,
            "category_totals": category_totals,
        })
        audit.record_pricing(cost)
        audit.record("pipeline_complete", f"Estimate generated: {cost.total_monthly} {cost.currency}/month.")

        all_assumptions = ai_assumptions + normalization_assumptions + service_assumptions

        return EstimateResult(
            estimate_id=estimate_id,
            project_name=working_requirement.project_name,
            strategy_used=strategy.value,
            original_request=requirement,
            normalized_spec=normalized_spec,
            assumptions=all_assumptions,
            validation=validation_report,
            architecture=architecture,
            cost=cost,
            audit_log=audit.log,
        )

    def _resolve_strategy(self, requirement: CustomerRequirement) -> NormalizationStrategy:
        if requirement.normalization_strategy:
            return NormalizationStrategy(requirement.normalization_strategy)
        return self.settings.default_normalization_strategy
