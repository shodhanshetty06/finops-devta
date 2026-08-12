"""
Celery task for async report generation.

Report generation (especially the 13-sheet Excel workbook, or a PDF with
charts) is the platform's heaviest single-request CPU cost. Moving it to a
worker keeps the API responsive under load and lets a slow report never
tie up an HTTP connection - the caller polls `GET /api/v1/jobs/{id}` (or
just waits, for small ones) instead.

Task arguments and return values must be JSON-serializable (see
`celery_app.py`'s `task_serializer="json"`), so this task receives plain
dicts (not `EstimateResult`/`BrandingConfig` instances) and re-validates
them via Pydantic inside the task body - the same trust boundary the HTTP
API applies to any request body.
"""
import base64
from datetime import datetime, timezone
from typing import Any, Literal

from app.domain.branding import BrandingConfig
from app.domain.estimate import EstimateResult
from app.reports.excel_generator import ExcelReportGenerator
from app.reports.pdf_generator import PdfReportGenerator
from app.tasks.celery_app import celery_app

ReportFormat = Literal["excel", "pdf"]

_CONTENT_TYPES: dict[str, str] = {
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}
_EXTENSIONS: dict[str, str] = {"excel": "xlsx", "pdf": "pdf"}


def _safe_filename(project_name: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in project_name).strip("_") or "estimate"


@celery_app.task(name="app.tasks.report_tasks.generate_report_task", bind=True)
def generate_report_task(
    self,
    estimate_json: dict[str, Any],
    branding_json: dict[str, Any],
    report_format: ReportFormat,
) -> dict[str, Any]:
    estimate = EstimateResult.model_validate(estimate_json)
    branding = BrandingConfig.model_validate(branding_json)

    if report_format == "excel":
        file_bytes = ExcelReportGenerator().generate(estimate, branding)
        suffix = "estimate"
    elif report_format == "pdf":
        file_bytes = PdfReportGenerator().generate(estimate, branding)
        suffix = "proposal"
    else:
        raise ValueError(f"Unknown report_format '{report_format}' - expected 'excel' or 'pdf'.")

    filename = (
        f"{_safe_filename(estimate.project_name)}_{suffix}_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d')}.{_EXTENSIONS[report_format]}"
    )
    return {
        "filename": filename,
        "content_type": _CONTENT_TYPES[report_format],
        "data_b64": base64.b64encode(file_bytes).decode("ascii"),
        "size_bytes": len(file_bytes),
    }
