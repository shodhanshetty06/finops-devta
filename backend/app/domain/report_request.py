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
