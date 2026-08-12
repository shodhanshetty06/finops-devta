"""
Region and scenario comparison engines.

Both reuse `EstimationService.generate_estimate` for every option - the
comparison is just running the existing, real pipeline multiple times and
diffing the results, never a separate pricing shortcut.
"""
from typing import Any

from app.core.exceptions import FinOpsError
from app.domain.enums import Region
from app.domain.optimization import (
    RegionComparison,
    RegionCostOption,
    ScenarioComparison,
    ScenarioComparisonRequest,
    ScenarioOutcome,
)
from app.domain.requirements import CustomerRequirement
from app.services.estimation_service import EstimationService


def _merge_overrides(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


class RegionComparisonEngine:
    def compare(
        self, requirement: CustomerRequirement, regions: list[str], estimation_service: EstimationService,
        *, force: bool = True,
    ) -> RegionComparison:
        options: list[RegionCostOption] = []
        currency = None
        for region_value in regions:
            try:
                region = Region(region_value)
            except ValueError:
                raise FinOpsError(f"Unsupported region '{region_value}'.", code="unsupported_region")
            variant = requirement.model_copy(update={"region": region})
            result = estimation_service.generate_estimate(variant, force=force)
            currency = result.cost.currency
            options.append(RegionCostOption(region=region.value, total_monthly=result.cost.total_monthly, currency=currency))

        if not options:
            raise FinOpsError("At least one region is required for comparison.", code="empty_comparison")

        cheapest = min(options, key=lambda o: o.total_monthly)
        most_expensive = max(options, key=lambda o: o.total_monthly)
        return RegionComparison(
            options=options,
            cheapest_region=cheapest.region,
            most_expensive_region=most_expensive.region,
            max_savings_monthly=round(most_expensive.total_monthly - cheapest.total_monthly, 2),
            currency=currency or "USD",
        )


class ScenarioComparisonEngine:
    def compare(self, request: ScenarioComparisonRequest, estimation_service: EstimationService) -> ScenarioComparison:
        base_result = estimation_service.generate_estimate(
            request.base, force=request.force, commitment_term_years=request.commitment_term_years,
        )
        base_cost = base_result.cost
        base_outcome = ScenarioOutcome(
            name="base", total_monthly=base_cost.total_monthly, total_yearly=base_cost.total_yearly,
            currency=base_cost.currency, delta_vs_base_monthly=0.0, delta_vs_base_percent=0.0,
        )

        base_dict = request.base.model_dump(mode="json")
        outcomes: list[ScenarioOutcome] = []
        for scenario in request.scenarios:
            merged = _merge_overrides(base_dict, scenario.overrides)
            try:
                variant = CustomerRequirement.model_validate(merged)
            except Exception as exc:
                raise FinOpsError(
                    f"Scenario '{scenario.name}' produced an invalid requirement: {exc}", code="invalid_scenario",
                ) from exc

            result = estimation_service.generate_estimate(
                variant, force=request.force, commitment_term_years=request.commitment_term_years,
            )
            cost = result.cost
            delta_monthly = round(cost.total_monthly - base_cost.total_monthly, 2)
            delta_percent = round((delta_monthly / base_cost.total_monthly) * 100, 2) if base_cost.total_monthly else 0.0
            outcomes.append(ScenarioOutcome(
                name=scenario.name, total_monthly=cost.total_monthly, total_yearly=cost.total_yearly,
                currency=cost.currency, delta_vs_base_monthly=delta_monthly, delta_vs_base_percent=delta_percent,
            ))

        return ScenarioComparison(base=base_outcome, scenarios=outcomes)
