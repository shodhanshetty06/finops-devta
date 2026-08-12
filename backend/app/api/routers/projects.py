"""
Project + versioned-estimate endpoints (Phase 3).

Every route requires authentication. `admin` can access any project;
`consultant`/`customer` can only access projects they own - enforced in
`ProjectService`, not duplicated here.

The estimate sub-resource endpoints are what turn Phase 1's stateless
`/api/v1/estimate` into real project history: each POST creates a new,
immutable, numbered version; nothing is ever overwritten in place.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_project_service
from app.core.config import Settings, get_settings
from app.core.exceptions import IntakeParseError
from app.core.uploads import read_upload_bounded
from app.db.models import EstimateVersionModel, ProjectModel, UserModel
from app.db.session import get_db
from app.domain.branding import BrandingConfig
from app.domain.estimate import EstimateResult
from app.domain.intake import TextIntakeRequest
from app.domain.optimization import BudgetStatus, VersionComparison
from app.domain.project import (
    EstimateVersionDetail,
    EstimateVersionRequest,
    EstimateVersionSummary,
    ProjectBudgetUpdate,
    ProjectCreate,
    ProjectRead,
)
from app.domain.requirements import CustomerRequirement
from app.intake.excel_parser import ExcelQuestionnaireParser
from app.intake.text_extractor import NaturalLanguageRequirementExtractor
from app.reports.excel_generator import ExcelReportGenerator
from app.reports.pdf_generator import PdfReportGenerator
from app.repositories.estimate_repository import EstimateVersionRepository
from app.services.project_service import ProjectService

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])


def _to_project_read(project: ProjectModel, latest_version: int | None) -> ProjectRead:
    return ProjectRead(
        id=project.id, name=project.name, owner_id=project.owner_id,
        created_at=project.created_at, updated_at=project.updated_at, latest_version=latest_version,
        monthly_budget_usd=project.monthly_budget_usd,
    )


def _to_summary(row: EstimateVersionModel) -> EstimateVersionSummary:
    return EstimateVersionSummary(
        version=row.version, estimate_id=row.estimate_id, created_at=row.created_at,
        created_by_id=row.created_by_id, total_monthly=row.total_monthly, currency=row.currency,
    )


def _to_detail(
    row: EstimateVersionModel, current_user: UserModel, budget_status: BudgetStatus | None = None,
) -> EstimateVersionDetail:
    result = EstimateResult.model_validate(row.result_json)
    if current_user.role != "admin":
        # The audit trail (every validation/normalization/pricing decision
        # the pipeline made) is an admin-only view - see EstimateResultView
        # on the frontend, which only renders the "Audit log" card for
        # user.role === "admin". Stripped here too so the raw API response
        # never carries it to non-admins regardless of UI.
        result = result.model_copy(update={"audit_log": result.audit_log.model_copy(update={"entries": []})})
    return EstimateVersionDetail(
        **_to_summary(row).model_dump(),
        request=CustomerRequirement.model_validate(row.request_json),
        result=result,
        budget_status=budget_status,
    )


@router.post("", response_model=ProjectRead, status_code=201, summary="Create a project")
def create_project(
    data: ProjectCreate,
    current_user: UserModel = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
):
    project = service.create_project(current_user, data.name)
    return _to_project_read(project, latest_version=None)


@router.get("", response_model=list[ProjectRead], summary="List projects (own projects, or all for admins)")
def list_projects(
    current_user: UserModel = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
):
    projects = service.list_projects(current_user)
    estimate_repo = EstimateVersionRepository(db)
    results = []
    for p in projects:
        latest = estimate_repo.get_latest(p.id)
        results.append(_to_project_read(p, latest_version=latest.version if latest else None))
    return results


@router.get("/{project_id}", response_model=ProjectRead, summary="Get a project")
def get_project(
    project_id: int,
    current_user: UserModel = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
):
    project = service.get_project(current_user, project_id)
    latest = EstimateVersionRepository(db).get_latest(project.id)
    return _to_project_read(project, latest_version=latest.version if latest else None)


@router.patch(
    "/{project_id}/budget", response_model=ProjectRead,
    summary="Set (or clear, with null) a project's monthly budget ceiling",
)
def update_project_budget(
    project_id: int,
    body: ProjectBudgetUpdate,
    current_user: UserModel = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
):
    project = service.set_budget(current_user, project_id, body.monthly_budget_usd)
    latest = EstimateVersionRepository(db).get_latest(project.id)
    return _to_project_read(project, latest_version=latest.version if latest else None)


@router.get(
    "/{project_id}/estimates/compare", response_model=VersionComparison,
    summary="Compare the total and per-category cost between two saved estimate versions",
)
def compare_estimate_versions(
    project_id: int,
    from_version: int = Query(..., alias="from", ge=1),
    to_version: int = Query(..., alias="to", ge=1),
    current_user: UserModel = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
):
    return service.compare_versions(current_user, project_id, from_version, to_version)


@router.post(
    "/{project_id}/estimates", response_model=EstimateVersionDetail, status_code=201,
    summary="Run the estimation pipeline and save the result as a new version",
)
def create_estimate_version(
    project_id: int,
    body: EstimateVersionRequest,
    current_user: UserModel = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
):
    version_row, _ = service.create_estimate_version(
        current_user, project_id, body.requirement,
        force=body.force, commitment_term_years=body.commitment_term_years,
    )
    project = service.get_project(current_user, project_id)
    budget_status = service.compute_budget_status(project, version_row.total_monthly)
    return _to_detail(version_row, current_user, budget_status)


@router.get(
    "/{project_id}/estimates", response_model=list[EstimateVersionSummary],
    summary="List saved estimate versions for a project",
)
def list_estimate_versions(
    project_id: int,
    current_user: UserModel = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
):
    return [_to_summary(row) for row in service.list_versions(current_user, project_id)]


@router.get(
    "/{project_id}/estimates/{version}", response_model=EstimateVersionDetail,
    summary="Reload a specific saved estimate version",
)
def get_estimate_version(
    project_id: int,
    version: int,
    current_user: UserModel = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
):
    # budget_status must be computed here too, not just on the
    # create-estimate-version response - otherwise reloading a saved
    # version (e.g. the frontend's project detail page, or simply
    # navigating back to it later) silently loses budget-overage
    # information that was present the moment the version was created.
    # Found during a live QA pass: setting a budget, then re-fetching an
    # existing version, always returned budget_status=null even though the
    # project had a budget configured.
    version_row = service.get_version(current_user, project_id, version)
    project = service.get_project(current_user, project_id)
    budget_status = service.compute_budget_status(project, version_row.total_monthly)
    return _to_detail(version_row, current_user, budget_status)


@router.post(
    "/{project_id}/estimates/{version}/reports/excel",
    summary="Export a saved estimate version as an Excel workbook",
)
def export_saved_version_excel(
    project_id: int,
    version: int,
    branding: BrandingConfig = BrandingConfig(),
    current_user: UserModel = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
):
    row = service.get_version(current_user, project_id, version)
    result = EstimateResult.model_validate(row.result_json)
    file_bytes = ExcelReportGenerator().generate(result, branding)
    filename = f"project{project_id}_v{version}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        iter([file_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/{project_id}/estimates/{version}/reports/pdf",
    summary="Export a saved estimate version as a PDF proposal",
)
def export_saved_version_pdf(
    project_id: int,
    version: int,
    branding: BrandingConfig = BrandingConfig(),
    current_user: UserModel = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
):
    row = service.get_version(current_user, project_id, version)
    result = EstimateResult.model_validate(row.result_json)
    file_bytes = PdfReportGenerator().generate(result, branding)
    filename = f"project{project_id}_v{version}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        iter([file_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# -- Phase 4: intake shortcuts -----------------------------------------------
# These parse/extract a requirement AND immediately save it as a new project
# version in one call - a convenience for already-trusted input. To review
# parse issues or extraction notes *before* committing to a saved version,
# use the stateless /api/v1/intake/* endpoints first and only POST the
# reviewed CustomerRequirement to /{project_id}/estimates once satisfied.

@router.post(
    "/{project_id}/intake/excel", response_model=EstimateVersionDetail, status_code=201,
    summary="Upload a filled-in Excel questionnaire and save the priced result as a new version",
)
async def create_estimate_version_from_excel(
    project_id: int,
    file: UploadFile,
    force: bool = Query(default=False),
    commitment_term_years: int = Query(default=0, ge=0, le=3),
    current_user: UserModel = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
    settings: Settings = Depends(get_settings),
):
    file_bytes = await read_upload_bounded(file, settings.max_upload_size_bytes)
    requirement, issues = ExcelQuestionnaireParser().parse(file_bytes)
    if requirement is None:
        detail = "; ".join(f"{i.field}: {i.message}" for i in issues) or "no usable fields were found"
        raise IntakeParseError(f"The questionnaire could not be parsed ({detail}).")

    version_row, _ = service.create_estimate_version(
        current_user, project_id, requirement, force=force, commitment_term_years=commitment_term_years,
    )
    return _to_detail(version_row, current_user)


@router.post(
    "/{project_id}/intake/text", response_model=EstimateVersionDetail, status_code=201,
    summary="Extract a requirement from free text and save the priced result as a new version",
)
def create_estimate_version_from_text(
    project_id: int,
    body: TextIntakeRequest,
    force: bool = Query(default=False),
    commitment_term_years: int = Query(default=0, ge=0, le=3),
    current_user: UserModel = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
):
    requirement, _notes = NaturalLanguageRequirementExtractor().extract(body.project_name, body.text, body.region_hint)
    version_row, _ = service.create_estimate_version(
        current_user, project_id, requirement, force=force, commitment_term_years=commitment_term_years,
    )
    return _to_detail(version_row, current_user)
