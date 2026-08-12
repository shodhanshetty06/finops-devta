"""
Committed Use Discount (CUD) recommendation engine.

Every discount percentage and dollar figure here comes straight from
`PricingEngine`/`PricingProvider.get_committed_use_discount_percent()` - the
same code path `/api/v1/estimate` already uses when a caller passes
`commitment_term_years`. This engine's only original contribution is
running that pipeline once per term (1yr, 3yr) and applying a documented,
workload-stability-aware recommendation on top of the results.

Limitation (documented, not hidden): this platform's pricing model treats a
CUD purely as a monthly rate discount (matching `PricingEngine`'s
implementation) and does not model an upfront payment option or a
cash-flow breakeven calculation - GCP's real "all upfront"/"partial
upfront" CUD payment options are out of scope for this phase.
"""
from app.domain.optimization import CommitmentRecommendation, CommitmentTermOption, WorkloadStability
from app.domain.requirements import CustomerRequirement
from app.services.estimation_service import EstimationService

DISCOUNTABLE_CATEGORIES = {"Compute", "GPU"}
CANDIDATE_TERMS = (1, 3)


class CommitmentEngine:
    def recommend(
        self,
        requirement: CustomerRequirement,
        estimation_service: EstimationService,
        *,
        workload_stability: WorkloadStability = WorkloadStability.STEADY,
        force: bool = False,
    ) -> CommitmentRecommendation:
        on_demand_result = estimation_service.generate_estimate(requirement, force=force, commitment_term_years=0)
        currency = on_demand_result.cost.currency
        discountable_amount = round(sum(
            li.monthly_amount for li in on_demand_result.cost.line_items if li.category in DISCOUNTABLE_CATEGORIES
        ), 2)

        options: list[CommitmentTermOption] = []
        for term in CANDIDATE_TERMS:
            term_result = estimation_service.generate_estimate(requirement, force=force, commitment_term_years=term)
            cud_discount = next(
                (d for d in term_result.cost.discounts if d.name == f"{term}-Year Committed Use Discount"), None
            )
            savings = cud_discount.monthly_savings if cud_discount else 0.0
            percent = cud_discount.percent_off if cud_discount else 0.0
            options.append(CommitmentTermOption(
                term_years=term,
                discount_percent=percent,
                monthly_cost_with_commitment=round(discountable_amount - savings, 2),
                monthly_savings_vs_on_demand=round(savings, 2),
                annual_savings_vs_on_demand=round(savings * 12, 2),
            ))

        if discountable_amount <= 0:
            return CommitmentRecommendation(
                on_demand_discountable_monthly_cost=discountable_amount,
                options=options,
                recommended_term_years=0,
                recommendation_reason="No compute or GPU spend was found in this estimate - there is nothing to commit to.",
                currency=currency,
            )

        if workload_stability == WorkloadStability.VARIABLE:
            return CommitmentRecommendation(
                on_demand_discountable_monthly_cost=discountable_amount,
                options=options,
                recommended_term_years=0,
                recommendation_reason=(
                    "Workload is marked variable/bursty - staying on-demand (with the automatic Sustained Use "
                    "Discount) avoids paying for committed capacity during low-usage periods. Reassess once usage "
                    "patterns stabilize."
                ),
                currency=currency,
            )

        best = max(options, key=lambda o: o.annual_savings_vs_on_demand)
        if best.annual_savings_vs_on_demand <= 0:
            return CommitmentRecommendation(
                on_demand_discountable_monthly_cost=discountable_amount,
                options=options,
                recommended_term_years=0,
                recommendation_reason="No committed-use discount is available for this configuration under the current pricing provider.",
                currency=currency,
            )

        return CommitmentRecommendation(
            on_demand_discountable_monthly_cost=discountable_amount,
            options=options,
            recommended_term_years=best.term_years,
            recommendation_reason=(
                f"Workload is marked steady - a {best.term_years}-year commitment offers the largest saving "
                f"({best.discount_percent:.0f}% off compute/GPU spend, ~{best.annual_savings_vs_on_demand:,.2f} "
                f"{currency}/year) with low risk of paying for unused capacity."
            ),
            currency=currency,
        )
