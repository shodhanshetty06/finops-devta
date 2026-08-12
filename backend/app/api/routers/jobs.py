"""
Async job endpoints (Phase 7): enqueue report generation or batch estimate
pricing onto Celery, then poll for status/result. Mirrors the synchronous
`/api/v1/reports/*` and `/api/v1/estimate` endpoints but returns
immediately with a job id instead of blocking the request for the full
computation - useful for large PDF/Excel exports or pricing many
requirements at once.

Kept stateless/unauthenticated like the synchronous endpoints they
parallel (`/api/v1/estimate`, `/api/v1/reports/*`); the heavier
per-endpoint rate limit (see app/middleware/rate_limit.py) is what protects
these from abuse instead of an auth requirement.
"""
import base64
import io
from typing import Any

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.domain.jobs import BatchEstimateJobRequest, JobEnqueuedResponse, JobStatusResponse, ReportJobRequest
from app.tasks.batch_tasks import generate_batch_estimates_task
from app.tasks.celery_app import celery_app
from app.tasks.report_tasks import generate_report_task

router = APIRouter(prefix="/api/v1/jobs", tags=["Async Jobs"])


@router.post(
    "/reports", response_model=JobEnqueuedResponse, status_code=202,
    summary="Enqueue async report generation (Excel or PDF)",
)
def enqueue_report_job(request: ReportJobRequest) -> JobEnqueuedResponse:
    async_result = generate_report_task.delay(
        request.estimate.model_dump(mode="json"),
        request.branding.model_dump(mode="json"),
        request.format,
    )
    return JobEnqueuedResponse(job_id=async_result.id)


@router.post(
    "/batch-estimate", response_model=JobEnqueuedResponse, status_code=202,
    summary="Enqueue pricing for a batch of customer requirements",
)
def enqueue_batch_estimate_job(request: BatchEstimateJobRequest) -> JobEnqueuedResponse:
    async_result = generate_batch_estimates_task.delay(
        [item.model_dump(mode="json") for item in request.items],
        request.force,
        request.commitment_term_years,
    )
    return JobEnqueuedResponse(job_id=async_result.id)


@router.get(
    "/{job_id}", response_model=JobStatusResponse,
    summary="Check an async job's status (and, once finished, its result)",
)
def get_job_status(job_id: str) -> JobStatusResponse:
    async_result = AsyncResult(job_id, app=celery_app)
    ready = async_result.ready()
    successful = async_result.successful() if ready else None
    error: str | None = None
    result: dict[str, Any] | None = None

    if ready:
        if successful:
            raw = async_result.result
            if isinstance(raw, dict) and "data_b64" in raw:
                # Report job: omit the (potentially multi-MB) base64 payload
                # from the status response - fetch it via .../download.
                result = {k: v for k, v in raw.items() if k != "data_b64"}
            else:
                result = raw
        else:
            error = str(async_result.result)

    return JobStatusResponse(
        job_id=job_id, state=async_result.state, ready=ready,
        successful=successful, error=error, result=result,
    )


@router.get("/{job_id}/download", summary="Download a completed report job's file")
def download_report_job(job_id: str):
    async_result = AsyncResult(job_id, app=celery_app)
    if not async_result.ready():
        raise HTTPException(status_code=425, detail="Job is not finished yet.")
    if not async_result.successful():
        raise HTTPException(status_code=422, detail=f"Job failed: {async_result.result}")

    raw = async_result.result
    if not isinstance(raw, dict) or "data_b64" not in raw:
        raise HTTPException(status_code=400, detail="This job is not a report generation job.")

    file_bytes = base64.b64decode(raw["data_b64"])
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=raw["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{raw["filename"]}"'},
    )
