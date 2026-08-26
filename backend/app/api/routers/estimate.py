"""Primary estimation endpoint: validate -> normalize -> architect -> price."""
from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_estimation_service
from app.domain.estimate import EstimateResult
from app.domain.region_resolution import resolve_region
from app.domain.requirements import CustomerRequirement
from app.services.estimation_service import EstimationService

router = APIRouter(prefix="/api/v1", tags=["Estimation"])


@router.post(
    "/estimate",
    response_model=EstimateResult,
    summary="Generate a full FinOps cost estimate",
    description=(
        "Runs the full pipeline: AI recommendation (if only business context was given), "
        "validation, normalization, architecture recommendation, and pricing. "
        "Returns every assumption, validation finding, and priced line item."
    ),
)
def create_estimate(
    requirement: CustomerRequirement,
    region: str | None = Query(
        default=None,
        description=(
            "Explicit region override, highest priority. When omitted, requirement.region is used "
            "as-is (already resolved to the workbook's region or the application default by whatever "
            "intake path produced it). The backend is the final authority on the resolved region - see "
            "app/domain/region_resolution.py - so a caller does not need to pre-merge an override into "
            "requirement.region itself; passing it here is equivalent and lets the backend validate it."
        ),
    ),
    force: bool = Query(default=False, description="Proceed even if blocker-severity validation findings exist."),
    commitment_term_years: int = Query(default=0, ge=0, le=3, description="0 = on-demand (Sustained Use Discount applied), 1 or 3 = Committed Use Discount."),
    service: EstimationService = Depends(get_estimation_service),
):
    resolved_region, _source = resolve_region(region, requirement.region.value)
    requirement = requirement.model_copy(update={"region": resolved_region})
    return service.generate_estimate(requirement, force=force, commitment_term_years=commitment_term_years)
