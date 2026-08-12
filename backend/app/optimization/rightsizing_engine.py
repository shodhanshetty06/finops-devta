"""
Rightsizing engine.

This platform has no live Cloud Monitoring integration, so utilization data
is a customer/consultant-supplied `UsageMetrics` input (see
`app/domain/optimization.py`). Given that input plus the customer's existing
`CustomerRequirement`, this engine proposes a resized `vcpu`/`ram_gb` and
re-runs it through the *real* estimation pipeline
(`EstimationService.generate_estimate`) to get a genuinely priced
before/after comparison - it never fabricates a monthly cost itself.

Sizing heuristic (documented, not hidden):
  - peak CPU utilization < IDLE_THRESHOLD -> recommend termination (idle resource).
  - peak CPU utilization < DOWNSIZE_THRESHOLD -> recommend downsizing so that,
    at the observed peak load, the *new* instance would run at roughly
    TARGET_PEAK_UTILIZATION (a conventional FinOps headroom target - big
    enough to absorb normal spikes, small enough to stop paying for idle
    capacity).
  - peak CPU utilization > UPSIZE_THRESHOLD -> recommend upsizing using the
    same target-utilization formula (the instance is at risk of throttling).
  - otherwise -> no change.

RAM is scaled by the same ratio as vCPU when only `avg_ram_utilization_percent`
is unavailable; if it is available, the engine computes a RAM scale ratio the
same way and applies whichever of the two (CPU-driven or RAM-driven) ratio is
larger, so the resized instance is never under-provisioned on either axis.
"""
import math

from app.domain.optimization import RightsizingAction, RightsizingFinding, RightsizingReport, UsageMetrics
from app.domain.requirements import CustomerRequirement
from app.services.estimation_service import EstimationService

IDLE_THRESHOLD_PERCENT = 5.0
DOWNSIZE_THRESHOLD_PERCENT = 40.0
UPSIZE_THRESHOLD_PERCENT = 85.0
TARGET_PEAK_UTILIZATION_PERCENT = 65.0

MIN_VCPU = 1
MIN_RAM_GB = 1.0


class RightsizingEngine:
    def analyze(
        self,
        requirement: CustomerRequirement,
        usage: UsageMetrics,
        estimation_service: EstimationService,
        *,
        force: bool = False,
    ) -> RightsizingReport:
        if requirement.compute is None:
            raise ValueError("Rightsizing requires a requirement with a `compute` section already specified.")

        current_result = estimation_service.generate_estimate(requirement, force=force)
        current_spec = current_result.normalized_spec
        current_cost = current_result.cost
        currency = current_cost.currency
        compute_line = next((li for li in current_cost.line_items if li.category == "Compute"
                              and li.sku_id and li.sku_id.startswith("compute-")), None)
        current_monthly = compute_line.monthly_amount if compute_line else 0.0
        description = current_spec.machine_type or "compute instance"

        if usage.peak_cpu_utilization_percent < IDLE_THRESHOLD_PERCENT and usage.avg_cpu_utilization_percent < IDLE_THRESHOLD_PERCENT:
            finding = RightsizingFinding(
                resource_description=description,
                action=RightsizingAction.TERMINATE_IDLE,
                reason=(
                    f"Peak CPU utilization over the last {usage.observation_period_days} day(s) was only "
                    f"{usage.peak_cpu_utilization_percent:.1f}% - this resource shows no meaningful load and is a "
                    "candidate for termination or archival rather than resizing."
                ),
                current_machine_type=description,
                current_monthly_cost=current_monthly,
                recommended_machine_type=None,
                recommended_monthly_cost=0.0,
                monthly_savings=round(current_monthly, 2),
                currency=currency,
            )
            return RightsizingReport(findings=[finding], total_monthly_savings=finding.monthly_savings, currency=currency)

        action = RightsizingAction.NO_CHANGE
        if usage.peak_cpu_utilization_percent < DOWNSIZE_THRESHOLD_PERCENT:
            action = RightsizingAction.DOWNSIZE
        elif usage.peak_cpu_utilization_percent > UPSIZE_THRESHOLD_PERCENT:
            action = RightsizingAction.UPSIZE

        if action == RightsizingAction.NO_CHANGE:
            finding = RightsizingFinding(
                resource_description=description,
                action=action,
                reason=(
                    f"Peak CPU utilization ({usage.peak_cpu_utilization_percent:.1f}%) is within the healthy "
                    f"{DOWNSIZE_THRESHOLD_PERCENT:.0f}-{UPSIZE_THRESHOLD_PERCENT:.0f}% band - no resizing recommended."
                ),
                current_machine_type=description,
                current_monthly_cost=current_monthly,
                recommended_machine_type=description,
                recommended_monthly_cost=current_monthly,
                monthly_savings=0.0,
                currency=currency,
            )
            return RightsizingReport(findings=[finding], total_monthly_savings=0.0, currency=currency)

        cpu_ratio = usage.peak_cpu_utilization_percent / TARGET_PEAK_UTILIZATION_PERCENT
        ratio = cpu_ratio
        if usage.avg_ram_utilization_percent is not None:
            ram_ratio = usage.avg_ram_utilization_percent / TARGET_PEAK_UTILIZATION_PERCENT
            ratio = max(cpu_ratio, ram_ratio)

        current_vcpu = requirement.compute.vcpu
        current_ram = requirement.compute.ram_gb
        round_fn = math.ceil if action == RightsizingAction.UPSIZE else math.floor
        new_vcpu = max(MIN_VCPU, round_fn(current_vcpu * ratio))
        new_ram = max(MIN_RAM_GB, round(current_ram * ratio, 1))

        if new_vcpu == current_vcpu and new_ram == current_ram:
            finding = RightsizingFinding(
                resource_description=description,
                action=RightsizingAction.NO_CHANGE,
                reason="Computed target size matches the current size after rounding - no change recommended.",
                current_machine_type=description,
                current_monthly_cost=current_monthly,
                recommended_machine_type=description,
                recommended_monthly_cost=current_monthly,
                monthly_savings=0.0,
                currency=currency,
            )
            return RightsizingReport(findings=[finding], total_monthly_savings=0.0, currency=currency)

        resized_requirement = requirement.model_copy(deep=True)
        resized_requirement.compute.vcpu = new_vcpu
        resized_requirement.compute.ram_gb = new_ram

        resized_result = estimation_service.generate_estimate(resized_requirement, force=True)
        resized_spec = resized_result.normalized_spec
        resized_compute_line = next((li for li in resized_result.cost.line_items if li.category == "Compute"
                                      and li.sku_id and li.sku_id.startswith("compute-")), None)
        recommended_monthly = resized_compute_line.monthly_amount if resized_compute_line else 0.0
        savings = round(current_monthly - recommended_monthly, 2)

        reason = (
            f"Peak CPU utilization was {usage.peak_cpu_utilization_percent:.1f}% over "
            f"{usage.observation_period_days} day(s) (avg {usage.avg_cpu_utilization_percent:.1f}%"
            + (f", avg RAM {usage.avg_ram_utilization_percent:.1f}%" if usage.avg_ram_utilization_percent is not None else "")
            + f"). Sized to target ~{TARGET_PEAK_UTILIZATION_PERCENT:.0f}% peak utilization on the recommended instance."
        )

        finding = RightsizingFinding(
            resource_description=description,
            action=action,
            reason=reason,
            current_machine_type=description,
            current_monthly_cost=current_monthly,
            recommended_machine_type=resized_spec.machine_type,
            recommended_monthly_cost=recommended_monthly,
            monthly_savings=savings,
            currency=currency,
        )
        return RightsizingReport(findings=[finding], total_monthly_savings=savings, currency=currency)
