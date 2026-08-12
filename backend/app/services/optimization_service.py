"""
OptimizationService: thin orchestration layer over the Phase 8 engines,
mirroring how `ProjectService` wraps `EstimationService` - routers depend on
this, never on the engines directly, so every optimization endpoint gets a
consistent construction pattern.
"""
from app.core.config import Settings
from app.domain.optimization import (
    CarbonEstimate,
    CloudComparison,
    CommitmentRecommendation,
    CostForecast,
    RegionComparison,
    RightsizingReport,
    ScenarioComparison,
    ScenarioComparisonRequest,
    UsageMetrics,
    WorkloadStability,
)
from app.domain.requirements import CustomerRequirement
from app.optimization.carbon_engine import CarbonEngine
from app.optimization.cloud_comparison_engine import CloudComparisonEngine
from app.optimization.comparison_engine import RegionComparisonEngine, ScenarioComparisonEngine
from app.optimization.commitment_engine import CommitmentEngine
from app.optimization.forecast_engine import ForecastEngine
from app.optimization.rightsizing_engine import RightsizingEngine
from app.services.estimation_service import EstimationService


class OptimizationService:
    def __init__(self, estimation_service: EstimationService, settings: Settings):
        self.estimation_service = estimation_service
        self.settings = settings
        self.rightsizing_engine = RightsizingEngine()
        self.commitment_engine = CommitmentEngine()
        self.forecast_engine = ForecastEngine()
        self.carbon_engine = CarbonEngine()
        self.region_engine = RegionComparisonEngine()
        self.scenario_engine = ScenarioComparisonEngine()
        self.cloud_engine = CloudComparisonEngine()

    def rightsizing(self, requirement: CustomerRequirement, usage: UsageMetrics, *, force: bool = False) -> RightsizingReport:
        return self.rightsizing_engine.analyze(requirement, usage, self.estimation_service, force=force)

    def commitment_recommendation(
        self, requirement: CustomerRequirement, *, workload_stability: WorkloadStability, force: bool = False,
    ) -> CommitmentRecommendation:
        return self.commitment_engine.recommend(
            requirement, self.estimation_service, workload_stability=workload_stability, force=force,
        )

    def forecast(
        self, requirement: CustomerRequirement, *, monthly_growth_percent: float, months: int,
        force: bool = False, commitment_term_years: int = 0,
    ) -> CostForecast:
        result = self.estimation_service.generate_estimate(
            requirement, force=force, commitment_term_years=commitment_term_years,
        )
        return self.forecast_engine.forecast(
            result.cost.total_monthly, monthly_growth_percent, months, result.cost.currency,
        )

    def carbon(self, requirement: CustomerRequirement, *, force: bool = False) -> CarbonEstimate:
        result = self.estimation_service.generate_estimate(requirement, force=force)
        return self.carbon_engine.estimate(result.normalized_spec)

    def compare_regions(self, requirement: CustomerRequirement, regions: list[str], *, force: bool = True) -> RegionComparison:
        return self.region_engine.compare(requirement, regions, self.estimation_service, force=force)

    def compare_scenarios(self, request: ScenarioComparisonRequest) -> ScenarioComparison:
        return self.scenario_engine.compare(request, self.estimation_service)

    def compare_clouds(self, requirement: CustomerRequirement, clouds: list[str], *, force: bool = True) -> CloudComparison:
        return self.cloud_engine.compare(requirement, clouds, self.settings, force=force)
