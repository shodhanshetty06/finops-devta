"""Request body shared by the Excel and PDF report endpoints: the estimate to
render plus optional branding overrides. Reports are generated from an
already-computed EstimateResult (the same object returned by POST
/api/v1/estimate) so exporting a report never re-runs pricing or risks
producing numbers that differ from what the user already reviewed."""
from pydantic import BaseModel

from app.domain.branding import BrandingConfig
from app.domain.estimate import EstimateResult


class ReportRequest(BaseModel):
    estimate: EstimateResult
    branding: BrandingConfig = BrandingConfig()
    # Opt-in (default off, so existing callers/tests see byte-for-byte the
    # same report unless they ask for this): when true, calls
    # ExplanationService to add customer-friendly, plain-English
    # explanations of the estimate's assumptions and an AI executive
    # summary to the generated report. Falls back to the report's existing
    # deterministic text if Groq isn't configured or the call fails - see
    # app/services/explanation_service.py.
    include_ai_explanations: bool = False
