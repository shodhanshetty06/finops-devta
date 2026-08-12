"""Project & versioned-estimate domain schemas (Phase 3; budget fields added Phase 8)."""
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.estimate import EstimateResult
from app.domain.optimization import BudgetStatus
from app.domain.requirements import CustomerRequirement


class ProjectCreate(BaseModel):
    name: str


class ProjectRead(BaseModel):
    id: int
    name: str
    owner_id: int
    created_at: datetime
    updated_at: datetime
    latest_version: int | None = None
    monthly_budget_usd: float | None = None


class ProjectBudgetUpdate(BaseModel):
    monthly_budget_usd: float | None = Field(default=None, ge=0, description="Set to null to remove the budget.")


class EstimateVersionRequest(BaseModel):
    requirement: CustomerRequirement
    force: bool = False
    commitment_term_years: int = 0


class EstimateVersionSummary(BaseModel):
    version: int
    estimate_id: str
    created_at: datetime
    created_by_id: int
    total_monthly: float
    currency: str


class EstimateVersionDetail(EstimateVersionSummary):
    request: CustomerRequirement
    result: EstimateResult
    budget_status: BudgetStatus | None = None
