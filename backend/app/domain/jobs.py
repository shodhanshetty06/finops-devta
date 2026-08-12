"""Domain schemas for Phase 7 async job endpoints (report generation and
batch estimate pricing, both run via Celery - see app/tasks/)."""
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.branding import BrandingConfig
from app.domain.estimate import EstimateResult
from app.domain.requirements import CustomerRequirement


class ReportJobRequest(BaseModel):
    estimate: EstimateResult
    branding: BrandingConfig = BrandingConfig()
    format: Literal["excel", "pdf"]


class BatchEstimateJobRequest(BaseModel):
    items: list[CustomerRequirement] = Field(min_length=1)
    force: bool = False
    commitment_term_years: int = 0


class JobEnqueuedResponse(BaseModel):
    job_id: str
    status: str = "queued"


class JobStatusResponse(BaseModel):
    job_id: str
    state: str  # Celery states: PENDING, STARTED, SUCCESS, FAILURE, RETRY
    ready: bool
    successful: bool | None = None
    error: str | None = None
    # For report jobs: {filename, content_type, size_bytes} once successful
    # (the file itself is fetched via GET /jobs/{id}/download, not inlined
    # here). For batch-estimate jobs: {total, succeeded, failed, items}.
    result: dict[str, Any] | None = None
