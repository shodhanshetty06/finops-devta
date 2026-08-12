"""Primary estimation endpoint: validate -> normalize -> architect -> price."""
from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_estimation_service
from app.domain.estimate import EstimateResult
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
    force: bool = Query(default=False, description="Proceed even if blocker-severity validation findings exist."),
    commitment_term_years: int = Query(default=0, ge=0, le=3, description="0 = on-demand (Sustained Use Discount applied), 1 or 3 = Committed Use Discount."),
    service: EstimationService = Depends(get_estimation_service),
):
    return service.generate_estimate(requirement, force=force, commitment_term_years=commitment_term_years)
