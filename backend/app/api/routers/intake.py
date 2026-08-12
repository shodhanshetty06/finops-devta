"""
Stateless input-ingestion endpoints (Phase 4): turn an uploaded Excel
questionnaire or a block of free-text business requirements into a
`CustomerRequirement`, optionally running it straight through the Phase 1
estimation pipeline.

These mirror `/api/v1/validate` and `/api/v1/estimate` in being stateless -
nothing is persisted. For the persisted version that saves directly into a
project's version history, see the `/api/v1/projects/{id}/intake/*`
endpoints in `projects.py`.
"""
from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_estimation_service
from app.core.config import Settings, get_settings
from app.core.uploads import read_upload_bounded
from app.domain.intake import IntakeResponse, TextIntakeRequest
from app.intake.excel_parser import ExcelQuestionnaireParser
from app.intake.excel_template import ExcelTemplateGenerator
from app.intake.text_extractor import NaturalLanguageRequirementExtractor
from app.services.estimation_service import EstimationService

router = APIRouter(prefix="/api/v1/intake", tags=["Intake"])


@router.get("/excel/template", summary="Download a blank Excel requirements questionnaire")
def download_excel_template():
    file_bytes = ExcelTemplateGenerator().generate()
    return StreamingResponse(
        iter([file_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="gcp_finops_questionnaire.xlsx"'},
    )


@router.post(
    "/excel", response_model=IntakeResponse,
    summary="Upload a filled-in Excel questionnaire and parse it into a requirement",
    description=(
        "Parses each field independently - a mistake in one section (e.g. an invalid machine family) "
        "is reported as an issue for that field/section only and never prevents the rest of the "
        "questionnaire from being read. Pass auto_estimate=true to also run the full estimation pipeline "
        "and return a priced EstimateResult in the same response."
    ),
)
async def upload_excel_questionnaire(
    file: UploadFile,
    auto_estimate: bool = Query(default=False),
    force: bool = Query(default=False),
    commitment_term_years: int = Query(default=0, ge=0, le=3),
    estimation_service: EstimationService = Depends(get_estimation_service),
    settings: Settings = Depends(get_settings),
):
    file_bytes = await read_upload_bounded(file, settings.max_upload_size_bytes)
    requirement, issues = ExcelQuestionnaireParser().parse(file_bytes)

    estimate = None
    if auto_estimate and requirement is not None:
        estimate = estimation_service.generate_estimate(requirement, force=force, commitment_term_years=commitment_term_years)

    return IntakeResponse(requirement=requirement, issues=issues, estimate=estimate)


@router.post(
    "/text", response_model=IntakeResponse,
    summary="Extract a requirement from free-text business requirements",
    description=(
        "Rule-based (regex/keyword) extraction of user counts, HA/uptime targets, database size, "
        "networking, and Kubernetes signals from free text - e.g. '500 users, HA required, 99.99% "
        "uptime, 100GB database'. Every inference is returned in `notes` with the reasoning behind it. "
        "This is NOT a hosted LLM call; see app/intake/text_extractor.py for the extraction rules."
    ),
)
def extract_from_text(
    body: TextIntakeRequest,
    auto_estimate: bool = Query(default=False),
    force: bool = Query(default=False),
    commitment_term_years: int = Query(default=0, ge=0, le=3),
    estimation_service: EstimationService = Depends(get_estimation_service),
):
    requirement, notes = NaturalLanguageRequirementExtractor().extract(body.project_name, body.text, body.region_hint)

    estimate = None
    if auto_estimate:
        estimate = estimation_service.generate_estimate(requirement, force=force, commitment_term_years=commitment_term_years)

    return IntakeResponse(requirement=requirement, notes=notes, estimate=estimate)
