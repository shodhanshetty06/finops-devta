"""Unit tests for the Phase 8 optimization engines, exercised directly
against the mock catalog/pricing provider (same pattern as
test_estimation_service.py) rather than through the API layer."""
import pytest

from app.domain.enums import DiskType, MachineFamily, Region
from app.domain.optimization import (
    RightsizingAction,
    ScenarioComparisonRequest,
    ScenarioRequest,
    UsageMetrics,
    WorkloadStability,
)
from app.domain.requirements import ComputeRequirement, CustomerRequirement, StorageRequirement
from app.optimization.carbon_engine import CarbonEngine
from app.optimization.comparison_engine import RegionComparisonEngine, ScenarioComparisonEngine
from app.optimization.commitment_engine import CommitmentEngine
from app.optimization.forecast_engine import ForecastEngine
from app.optimization.rightsizing_engine import RightsizingEngine
from app.services.estimation_service import EstimationService


@pytest.fixture
def estimation_service(catalog, pricing_provider, settings):
    return EstimationService(catalog=catalog, pricing_provider=pricing_provider, settings=settings)


def _compute_requirement(vcpu=8, ram_gb=32, instance_count=1, region=Region.US_CENTRAL1):
    return CustomerRequirement(
        project_name="Rightsizing Target",
        region=region,
        normalization_strategy="balanced",
        compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=vcpu, ram_gb=ram_gb, instance_count=instance_count),
        storage=StorageRequirement(disk_type=DiskType.PD_BALANCED, size_gb=100),
    )


# -- Rightsizing --------------------------------------------------------

def test_rightsizing_recommends_termination_for_idle_resource(estimation_service):
    req = _compute_requirement()
    usage = UsageMetrics(avg_cpu_utilization_percent=1.0, peak_cpu_utilization_percent=2.0, observation_period_days=30)

    report = RightsizingEngine().analyze(req, usage, estimation_service)

    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.action == RightsizingAction.TERMINATE_IDLE
    assert finding.recommended_monthly_cost == 0.0
    assert finding.monthly_savings == finding.current_monthly_cost
    assert report.total_monthly_savings == finding.monthly_savings


def test_rightsizing_recommends_downsize_for_low_utilization(estimation_service):
    req = _compute_requirement(vcpu=8, ram_gb=32)
    usage = UsageMetrics(avg_cpu_utilization_percent=15.0, peak_cpu_utilization_percent=20.0, observation_period_days=30)

    report = RightsizingEngine().analyze(req, usage, estimation_service)

    finding = report.findings[0]
    assert finding.action == RightsizingAction.DOWNSIZE
    assert finding.recommended_machine_type is not None
    assert finding.recommended_monthly_cost < finding.current_monthly_cost
    assert finding.monthly_savings > 0
    assert report.total_monthly_savings == finding.monthly_savings


def test_rightsizing_recommends_upsize_for_high_utilization(estimation_service):
    req = _compute_requirement(vcpu=2, ram_gb=8)
    usage = UsageMetrics(avg_cpu_utilization_percent=90.0, peak_cpu_utilization_percent=97.0, observation_period_days=30)

    report = RightsizingEngine().analyze(req, usage, estimation_service)

    finding = report.findings[0]
    assert finding.action == RightsizingAction.UPSIZE
    assert finding.recommended_monthly_cost > finding.current_monthly_cost
    assert finding.monthly_savings < 0  # a "saving" of negative amount = it costs more


def test_rightsizing_recommends_no_change_for_healthy_utilization(estimation_service):
    req = _compute_requirement(vcpu=8, ram_gb=32)
    usage = UsageMetrics(avg_cpu_utilization_percent=55.0, peak_cpu_utilization_percent=60.0, observation_period_days=30)

    report = RightsizingEngine().analyze(req, usage, estimation_service)

    finding = report.findings[0]
    assert finding.action == RightsizingAction.NO_CHANGE
    assert finding.monthly_savings == 0.0


def test_rightsizing_requires_compute_section(estimation_service):
    req = CustomerRequirement(project_name="No compute", region=Region.US_CENTRAL1)
    usage = UsageMetrics(avg_cpu_utilization_percent=10.0, peak_cpu_utilization_percent=20.0)

    with pytest.raises(ValueError):
        RightsizingEngine().analyze(req, usage, estimation_service)


# -- Commitment recommendation -------------------------------------------

def test_commitment_recommends_term_for_steady_workload(estimation_service):
    req = _compute_requirement(vcpu=8, ram_gb=32)

    rec = CommitmentEngine().recommend(req, estimation_service, workload_stability=WorkloadStability.STEADY)

    assert rec.on_demand_discountable_monthly_cost > 0
    assert {o.term_years for o in rec.options} == {1, 3}
    assert rec.recommended_term_years in (0, 1, 3)
    if rec.recommended_term_years:
        chosen = next(o for o in rec.options if o.term_years == rec.recommended_term_years)
        assert chosen.monthly_savings_vs_on_demand > 0
        # 3-year should never save less than 1-year for this mock provider's discount curve.
        three_yr = next(o for o in rec.options if o.term_years == 3)
        one_yr = next(o for o in rec.options if o.term_years == 1)
        assert three_yr.discount_percent >= one_yr.discount_percent


def test_commitment_recommends_on_demand_for_variable_workload(estimation_service):
    req = _compute_requirement(vcpu=8, ram_gb=32)

    rec = CommitmentEngine().recommend(req, estimation_service, workload_stability=WorkloadStability.VARIABLE)

    assert rec.recommended_term_years == 0
    assert "variable" in rec.recommendation_reason.lower()


class _NoComputeSpendEstimationService:
    """Wraps a real EstimationService but strips Compute/GPU line items from
    the result, simulating a requirement with zero discountable spend. Used
    instead of a bare storage-only CustomerRequirement because `compute=None`
    always triggers the AI recommendation engine's default sizing (so a
    genuinely $0-compute estimate can't be produced through the real
    pipeline) - this still exercises CommitmentEngine's own zero-spend branch
    against a structurally valid EstimateResult."""

    def __init__(self, inner: EstimationService):
        self.inner = inner

    def generate_estimate(self, requirement, *, force=False, commitment_term_years=0):
        result = self.inner.generate_estimate(requirement, force=force, commitment_term_years=commitment_term_years)
        remaining = [li for li in result.cost.line_items if li.category not in ("Compute", "GPU")]
        subtotal = round(sum(li.monthly_amount for li in remaining), 2)
        new_cost = result.cost.model_copy(update={
            "line_items": remaining, "discounts": [],
            "subtotal_monthly": subtotal, "discount_total_monthly": 0.0,
            "total_monthly": subtotal, "total_yearly": round(subtotal * 12, 2), "total_three_year": round(subtotal * 36, 2),
        })
        return result.model_copy(update={"cost": new_cost})


def test_commitment_with_no_discountable_spend(estimation_service):
    req = _compute_requirement()
    wrapped_service = _NoComputeSpendEstimationService(estimation_service)

    rec = CommitmentEngine().recommend(req, wrapped_service, workload_stability=WorkloadStability.STEADY)

    assert rec.on_demand_discountable_monthly_cost == 0
    assert rec.recommended_term_years == 0


# -- Forecast -------------------------------------------------------------

def test_forecast_compounds_growth_monthly():
    forecast = ForecastEngine().forecast(
        starting_monthly_cost=1000.0, monthly_growth_percent=10.0, months=3, currency="USD",
    )

    assert forecast.months == 3
    assert len(forecast.points) == 3
    assert forecast.points[0].projected_monthly_cost == 1000.0
    assert forecast.points[1].projected_monthly_cost == 1100.0
    assert forecast.points[2].projected_monthly_cost == 1210.0
    assert forecast.points[-1].cumulative_cost == forecast.total_projected_cost
    assert forecast.total_projected_cost == round(1000 + 1100 + 1210, 2)


def test_forecast_zero_growth_is_flat():
    forecast = ForecastEngine().forecast(starting_monthly_cost=500.0, monthly_growth_percent=0.0, months=4, currency="USD")
    assert all(p.projected_monthly_cost == 500.0 for p in forecast.points)


def test_forecast_rejects_out_of_range_months():
    with pytest.raises(ValueError):
        ForecastEngine().forecast(starting_monthly_cost=100.0, monthly_growth_percent=1.0, months=0, currency="USD")
    with pytest.raises(ValueError):
        ForecastEngine().forecast(starting_monthly_cost=100.0, monthly_growth_percent=1.0, months=61, currency="USD")


# -- Carbon -----------------------------------------------------------------

def test_carbon_estimate_scales_with_vcpu(estimation_service):
    small = estimation_service.generate_estimate(_compute_requirement(vcpu=2, ram_gb=8)).normalized_spec
    large = estimation_service.generate_estimate(_compute_requirement(vcpu=16, ram_gb=64)).normalized_spec

    engine = CarbonEngine()
    small_estimate = engine.estimate(small)
    large_estimate = engine.estimate(large)

    assert small_estimate.estimated_kgco2e_per_month > 0
    assert large_estimate.estimated_kgco2e_per_month > small_estimate.estimated_kgco2e_per_month
    assert "illustrative" in small_estimate.methodology_note.lower()


def test_carbon_estimate_varies_by_region(estimation_service):
    us_west = estimation_service.generate_estimate(_compute_requirement(region=Region.US_WEST1)).normalized_spec
    asia_south = estimation_service.generate_estimate(_compute_requirement(region=Region.ASIA_SOUTH1)).normalized_spec

    engine = CarbonEngine()
    low_carbon = engine.estimate(us_west)
    high_carbon = engine.estimate(asia_south)

    # us-west1 (hydro-heavy, in our illustrative table) should be cleaner than asia-south1 (coal-heavy).
    assert low_carbon.estimated_kgco2e_per_month < high_carbon.estimated_kgco2e_per_month


# -- Region / scenario comparison -----------------------------------------

def test_region_comparison_orders_options(estimation_service):
    req = _compute_requirement()
    comparison = RegionComparisonEngine().compare(
        req, ["us-central1", "us-west1", "asia-south1"], estimation_service,
    )

    assert len(comparison.options) == 3
    prices = {o.region: o.total_monthly for o in comparison.options}
    cheapest = min(prices, key=prices.get)
    most_expensive = max(prices, key=prices.get)
    assert comparison.cheapest_region == cheapest
    assert comparison.most_expensive_region == most_expensive
    assert comparison.max_savings_monthly == round(prices[most_expensive] - prices[cheapest], 2)


def test_region_comparison_rejects_unsupported_region(estimation_service):
    from app.core.exceptions import FinOpsError
    with pytest.raises(FinOpsError):
        RegionComparisonEngine().compare(_compute_requirement(), ["mars-north1"], estimation_service)


def test_scenario_comparison_prices_overrides_against_base(estimation_service):
    base = _compute_requirement(vcpu=4, ram_gb=16)
    request = ScenarioComparisonRequest(
        base=base,
        scenarios=[
            ScenarioRequest(name="bigger", overrides={"compute": {"vcpu": 16, "ram_gb": 64}}),
            ScenarioRequest(name="different-region", overrides={"region": "europe-west1"}),
        ],
    )

    comparison = ScenarioComparisonEngine().compare(request, estimation_service)

    assert comparison.base.delta_vs_base_monthly == 0.0
    assert len(comparison.scenarios) == 2
    bigger = next(s for s in comparison.scenarios if s.name == "bigger")
    assert bigger.total_monthly > comparison.base.total_monthly
    assert bigger.delta_vs_base_monthly > 0
    assert bigger.delta_vs_base_percent > 0


def test_scenario_comparison_rejects_invalid_override(estimation_service):
    from app.core.exceptions import FinOpsError
    base = _compute_requirement()
    request = ScenarioComparisonRequest(
        base=base,
        scenarios=[ScenarioRequest(name="broken", overrides={"compute": {"vcpu": -5}})],
    )
    with pytest.raises(FinOpsError):
        ScenarioComparisonEngine().compare(request, estimation_service)
