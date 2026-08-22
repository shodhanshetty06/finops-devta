"""
Report export endpoints.

Both endpoints accept a `ReportRequest` (an already-computed `EstimateResult`
- the same object POST /api/v1/estimate returns - plus optional branding) and
stream back a file. Reports never recompute pricing; they only render the
estimate that was already validated, normalized, and priced.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.domain.explanation import EstimateExplanation
from app.domain.report_request import ReportRequest
from app.reports.excel_generator import ExcelReportGenerator
from app.reports.pdf_generator import PdfReportGenerator
from app.services.explanation_service import ExplanationService, get_explanation_service

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


def _safe_filename(project_name: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in project_name).strip("_") or "estimate"


def _maybe_explain(request: ReportRequest, service: ExplanationService) -> EstimateExplanation | None:
    # Opt-in per request.include_ai_explanations - see ReportRequest.
    # ExplanationService always returns a complete result (falling back to
    # template text internally), so a report never fails or blocks because
    # of this - only skipped entirely when not requested.
    if not request.include_ai_explanations:
        return None
    return service.explain_estimate(request.estimate)


@router.post(
    "/excel",
    summary="Export an estimate as a formatted Excel workbook",
    description=(
        "Renders the 13-sheet enterprise pricing workbook (Summary, Compute, Storage, Database, "
        "Networking, Licensing, Assumptions, Validation, Recommendations, Pricing, Totals, Yearly Cost, "
        "Audit) from an already-computed EstimateResult. Includes live Excel SUM formulas, not just "
        "static numbers. Set include_ai_explanations=true to add Groq-generated customer-friendly "
        "explanations of assumptions alongside the existing deterministic reasons."
    ),
)
def export_excel(request: ReportRequest, explanation_service: ExplanationService = Depends(get_explanation_service)):
    explanation = _maybe_explain(request, explanation_service)
    generator = ExcelReportGenerator()
    file_bytes = generator.generate(request.estimate, request.branding, explanation)
    filename = f"{_safe_filename(request.estimate.project_name)}_estimate_{datetime.now(timezone.utc).strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        iter([file_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/pdf",
    summary="Export an estimate as a client-ready PDF proposal",
    description=(
        "Renders a PDF proposal (executive summary, architecture, pricing, charts, assumptions, "
        "validation results, savings opportunities, totals, signature area) from an already-computed "
        "EstimateResult. Set include_ai_explanations=true to add a Groq-generated customer-friendly "
        "summary and assumption explanations alongside the existing deterministic text."
    ),
)
def export_pdf(request: ReportRequest, explanation_service: ExplanationService = Depends(get_explanation_service)):
    explanation = _maybe_explain(request, explanation_service)
    generator = PdfReportGenerator()
    file_bytes = generator.generate(request.estimate, request.branding, explanation)
    filename = f"{_safe_filename(request.estimate.project_name)}_proposal_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        iter([file_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
