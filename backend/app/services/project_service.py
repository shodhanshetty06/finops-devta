"""
ProjectService: orchestrates project + versioned-estimate persistence on top
of `EstimationService` (Phase 1) and the repository layer (Phase 3).

RBAC rule (kept intentionally simple for this phase): `admin` can access any
project; `consultant` and `customer` can only access projects they own.
Broader sharing/collaboration (e.g. a consultant managing a customer's
project) is a natural Phase-3.x follow-up, not needed for the core
persistence/auth/versioning capability this phase delivers.
"""
from app.core.exceptions import ForbiddenError, ResourceNotFoundError
from app.db.models import EstimateVersionModel, ProjectModel, UserModel
from app.domain.estimate import EstimateResult
from app.domain.optimization import BudgetStatus, VersionComparison
from app.domain.pricing import CostBreakdown
from app.domain.requirements import CustomerRequirement
from app.repositories.estimate_repository import EstimateVersionRepository
from app.repositories.project_repository import ProjectRepository
from app.services.estimation_service import EstimationService

ADMIN_ROLE = "admin"


def _category_totals(cost: CostBreakdown) -> dict[str, float]:
    totals: dict[str, float] = {}
    for item in cost.line_items:
        totals[item.category] = round(totals.get(item.category, 0.0) + item.monthly_amount, 2)
    return totals


class ProjectService:
    def __init__(
        self,
        project_repo: ProjectRepository,
        estimate_repo: EstimateVersionRepository,
        estimation_service: EstimationService,
    ):
        self.project_repo = project_repo
        self.estimate_repo = estimate_repo
        self.estimation_service = estimation_service

    def create_project(self, user: UserModel, name: str) -> ProjectModel:
        return self.project_repo.create(name=name, owner_id=user.id)

    def list_projects(self, user: UserModel) -> list[ProjectModel]:
        if user.role == ADMIN_ROLE:
            return self.project_repo.list_all()
        return self.project_repo.list_for_owner(user.id)

    def get_project(self, user: UserModel, project_id: int) -> ProjectModel:
        project = self.project_repo.get_by_id(project_id)
        if project is None:
            raise ResourceNotFoundError(f"Project {project_id} does not exist.")
        self._authorize(user, project)
        return project

    def create_estimate_version(
        self, user: UserModel, project_id: int, requirement: CustomerRequirement,
        *, force: bool = False, commitment_term_years: int = 0,
    ) -> tuple[EstimateVersionModel, EstimateResult]:
        project = self.get_project(user, project_id)
        result = self.estimation_service.generate_estimate(
            requirement, force=force, commitment_term_years=commitment_term_years,
        )
        version_row = self.estimate_repo.add_version(
            project_id=project.id, requirement=requirement, result=result, created_by_id=user.id,
        )
        return version_row, result

    def list_versions(self, user: UserModel, project_id: int) -> list[EstimateVersionModel]:
        self.get_project(user, project_id)  # authorizes
        return self.estimate_repo.list_versions(project_id)

    def get_version(self, user: UserModel, project_id: int, version: int) -> EstimateVersionModel:
        self.get_project(user, project_id)  # authorizes
        version_row = self.estimate_repo.get_version(project_id, version)
        if version_row is None:
            raise ResourceNotFoundError(f"Version {version} of project {project_id} does not exist.")
        return version_row

    def set_budget(self, user: UserModel, project_id: int, monthly_budget_usd: float | None) -> ProjectModel:
        project = self.get_project(user, project_id)  # authorizes
        return self.project_repo.update_budget(project, monthly_budget_usd)

    def compare_versions(self, user: UserModel, project_id: int, from_version: int, to_version: int) -> VersionComparison:
        self.get_project(user, project_id)  # authorizes
        from_row = self.get_version(user, project_id, from_version)
        to_row = self.get_version(user, project_id, to_version)

        from_cost = EstimateResult.model_validate(from_row.result_json).cost
        to_cost = EstimateResult.model_validate(to_row.result_json).cost
        from_by_category = _category_totals(from_cost)
        to_by_category = _category_totals(to_cost)
        category_deltas = {
            category: round(to_by_category.get(category, 0.0) - from_by_category.get(category, 0.0), 2)
            for category in set(from_by_category) | set(to_by_category)
        }

        delta_monthly = round(to_row.total_monthly - from_row.total_monthly, 2)
        delta_percent = round((delta_monthly / from_row.total_monthly) * 100, 2) if from_row.total_monthly else 0.0

        return VersionComparison(
            from_version=from_version, to_version=to_version,
            from_total_monthly=from_row.total_monthly, to_total_monthly=to_row.total_monthly,
            delta_monthly=delta_monthly, delta_percent=delta_percent, currency=to_row.currency,
            category_deltas=category_deltas,
        )

    @staticmethod
    def compute_budget_status(project: ProjectModel, actual_monthly: float) -> BudgetStatus:
        budget = project.monthly_budget_usd
        if budget is None:
            return BudgetStatus(
                budget_monthly=None, actual_monthly=actual_monthly,
                within_budget=None, overage_amount=None, overage_percent=None,
            )
        overage = round(actual_monthly - budget, 2)
        within_budget = overage <= 0
        return BudgetStatus(
            budget_monthly=budget, actual_monthly=actual_monthly, within_budget=within_budget,
            overage_amount=max(overage, 0.0),
            overage_percent=round((max(overage, 0.0) / budget) * 100, 2) if budget else 0.0,
        )

    def _authorize(self, user: UserModel, project: ProjectModel) -> None:
        if user.role != ADMIN_ROLE and project.owner_id != user.id:
            raise ForbiddenError("You do not have access to this project.")
