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
    # Optional ISO currency code (e.g. "INR") to render the report in,
    # matching the frontend's own display-currency selector
    # (frontend/src/contexts/currency-context.tsx). Purely presentational,
    # exactly like that selector - never re-prices anything; every figure
    # is rescaled by a single fetched exchange rate via
    # CurrencyConverter.convert_estimate (app/pricing/currency_converter.py).
    # Unset, or equal to the estimate's own currency, means no conversion -
    # the default, so existing callers see the same native-currency report
    # as before. If a rate isn't available, the report falls back to the
    # estimate's native currency rather than failing the export.
    target_currency: str | None = None
