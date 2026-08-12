"""
Phase 8 FinOps optimization endpoints: rightsizing, committed-use discount
recommendations, cost forecasting, carbon footprint estimation, and
region/scenario comparison. All require authentication (any role) - these
are read-only analyses over a submitted `CustomerRequirement`, not tied to a
saved project, so no ownership check applies (compare to `/projects/*`,
which does gate on project ownership).
"""
from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_optimization_service
from app.db.models import UserModel
from app.domain.optimization import (
    CarbonEstimate,
    CarbonRequest,
    CloudComparison,
    CloudComparisonRequest,
    CommitmentRecommendation,
    CommitmentRequest,
    CostForecast,
    ForecastRequest,
    RegionComparison,
    RegionComparisonRequest,
    RightsizingReport,
    RightsizingRequest,
    ScenarioComparison,
    ScenarioComparisonRequest,
)
from app.services.optimization_service import OptimizationService

router = APIRouter(prefix="/api/v1/optimization", tags=["Optimization"])


@router.post(
    "/rightsizing", response_model=RightsizingReport,
    summary="Recommend downsize/upsize/termination based on supplied utilization metrics",
)
def rightsizing(
    body: RightsizingRequest,
    _user: UserModel = Depends(get_current_user),
    service: OptimizationService = Depends(get_optimization_service),
):
    return service.rightsizing(body.requirement, body.usage, force=body.force)


@router.post(
    "/commitment-recommendation", response_model=CommitmentRecommendation,
    summary="Recommend a Committed Use Discount term (or none) for a given workload",
)
def commitment_recommendation(
    body: CommitmentRequest,
    _user: UserModel = Depends(get_current_user),
    service: OptimizationService = Depends(get_optimization_service),
):
    return service.commitment_recommendation(body.requirement, workload_stability=body.workload_stability, force=body.force)


@router.post(
    "/forecast", response_model=CostForecast,
    summary="Project monthly cost forward under a supplied growth-rate assumption",
)
def forecast(
    body: ForecastRequest,
    _user: UserModel = Depends(get_current_user),
    service: OptimizationService = Depends(get_optimization_service),
):
    return service.forecast(
        body.requirement, monthly_growth_percent=body.monthly_growth_percent, months=body.months,
        force=body.force, commitment_term_years=body.commitment_term_years,
    )


@router.post(
    "/carbon", response_model=CarbonEstimate,
    summary="Estimate the monthly carbon footprint of the priced compute configuration",
)
def carbon(
    body: CarbonRequest,
    _user: UserModel = Depends(get_current_user),
    service: OptimizationService = Depends(get_optimization_service),
):
    return service.carbon(body.requirement, force=body.force)


@router.post(
    "/compare-regions", response_model=RegionComparison,
    summary="Price the same configuration across multiple regions",
)
def compare_regions(
    body: RegionComparisonRequest,
    _user: UserModel = Depends(get_current_user),
    service: OptimizationService = Depends(get_optimization_service),
):
    return service.compare_regions(body.requirement, body.regions, force=body.force)


@router.post(
    "/compare-scenarios", response_model=ScenarioComparison,
    summary="Price a base requirement against one or more named override scenarios",
)
def compare_scenarios(
    body: ScenarioComparisonRequest,
    _user: UserModel = Depends(get_current_user),
    service: OptimizationService = Depends(get_optimization_service),
):
    return service.compare_scenarios(body)


@router.post(
    "/compare-clouds", response_model=CloudComparison,
    summary="Price the same configuration across GCP, AWS, and Azure (Phase 9)",
)
def compare_clouds(
    body: CloudComparisonRequest,
    _user: UserModel = Depends(get_current_user),
    service: OptimizationService = Depends(get_optimization_service),
):
    return service.compare_clouds(body.requirement, body.clouds, force=body.force)
