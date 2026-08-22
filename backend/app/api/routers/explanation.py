"""
LLM-assisted explanation endpoints (Groq - see app/llm/groq_provider.py).

Both endpoints take an already-computed result - the same EstimateResult
POST /api/v1/estimate returns, or the same ScenarioComparison POST
/api/v1/optimization/compare-scenarios returns - and return customer-
friendly prose about it. Neither endpoint recomputes or changes a price,
SKU, currency, or configuration; see app/services/explanation_service.py.
Public/unauthenticated like /reports and /assistant: no user- or account-
specific data is involved, only prose about numbers the caller already
has. Listed under FINOPS_RATE_LIMIT_HEAVY_PATH_PREFIXES since a successful
call has a real per-request cost, same reasoning as /assistant.

Always returns 200 - if Groq isn't configured, times out, is rate-limited,
or fails, the response is still complete, just built from deterministic
template text instead (see ExplanationService._complete). There is no
"unavailable" error response for this feature by design.
"""
from fastapi import APIRouter, Depends

from app.domain.explanation import (
    EstimateExplanation,
    EstimateExplanationRequest,
    ScenarioComparisonExplanation,
    ScenarioComparisonExplanationRequest,
)
from app.services.explanation_service import ExplanationService, get_explanation_service

router = APIRouter(prefix="/api/v1/explanations", tags=["Explanations"])


@router.post(
    "/estimate",
    response_model=EstimateExplanation,
    summary="Generate customer-friendly explanations for an estimate's assumptions and priced resources",
    description=(
        "Explains, in plain English, every normalization assumption and priced resource on an already-"
        "computed EstimateResult - what was requested, what was used instead and why, and what each "
        "resource costs. Never recalculates a price or changes a value; falls back to deterministic "
        "template text if Groq isn't configured or the call fails."
    ),
)
def explain_estimate(
    body: EstimateExplanationRequest,
    service: ExplanationService = Depends(get_explanation_service),
) -> EstimateExplanation:
    return service.explain_estimate(body.estimate)


@router.post(
    "/scenario-comparison",
    response_model=ScenarioComparisonExplanation,
    summary="Generate a customer-friendly explanation of an upgrade/downgrade cost comparison",
    description=(
        "Explains, in plain English, an already-computed ScenarioComparison (POST "
        "/api/v1/optimization/compare-scenarios) - whether each scenario is a saving or an additional cost "
        "versus the base, using the exact monthly/annual delta already computed. Never recalculates a price."
    ),
)
def explain_scenario_comparison(
    body: ScenarioComparisonExplanationRequest,
    service: ExplanationService = Depends(get_explanation_service),
) -> ScenarioComparisonExplanation:
    return service.explain_scenario_comparison(body.comparison)
