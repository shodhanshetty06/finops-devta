"""
Domain schemas for Phase 8 FinOps optimization features: rightsizing,
committed-use recommendations, cost forecasting, carbon footprint
estimation, region/scenario comparison, and budget tracking.

Every dollar figure in this module is still produced by the same
`PricingProvider`/`PricingEngine` the rest of the platform uses - nothing
here invents a price. Where a feature needs an input this platform has no
live data source for (utilization metrics, growth rate, workload
stability), that input is explicitly customer/consultant-supplied, not
inferred - consistent with the "never hide assumptions" principle the
validation/normalization layers already follow.
"""
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.domain.requirements import CustomerRequirement


# -- Rightsizing ------------------------------------------------------------

class UsageMetrics(BaseModel):
    """Observed utilization for the compute resource being evaluated. This
    platform has no live Cloud Monitoring integration (see
    docs/ROADMAP.md Phase 9+) - these are customer/consultant-supplied
    values, e.g. exported from Cloud Monitoring or a third-party APM."""

    avg_cpu_utilization_percent: float = Field(ge=0, le=100)
    peak_cpu_utilization_percent: float = Field(ge=0, le=100)
    avg_ram_utilization_percent: float | None = Field(default=None, ge=0, le=100)
    observation_period_days: int = Field(default=30, gt=0)


class RightsizingAction(str, Enum):
    DOWNSIZE = "downsize"
    UPSIZE = "upsize"
    TERMINATE_IDLE = "terminate_idle"
    NO_CHANGE = "no_change"


class RightsizingFinding(BaseModel):
    resource_description: str
    action: RightsizingAction
    reason: str
    current_machine_type: str
    current_monthly_cost: float
    recommended_machine_type: str | None = None
    recommended_monthly_cost: float | None = None
    monthly_savings: float = 0.0
    currency: str


class RightsizingReport(BaseModel):
    findings: list[RightsizingFinding]
    total_monthly_savings: float
    currency: str


class RightsizingRequest(BaseModel):
    requirement: CustomerRequirement
    usage: UsageMetrics
    force: bool = False


# -- Committed Use Discount recommendation -----------------------------

class WorkloadStability(str, Enum):
    STEADY = "steady"      # runs continuously / predictably - a commitment is low-risk
    VARIABLE = "variable"  # bursty/seasonal - a commitment risks paying for unused capacity


class CommitmentTermOption(BaseModel):
    term_years: int
    discount_percent: float
    monthly_cost_with_commitment: float
    monthly_savings_vs_on_demand: float
    annual_savings_vs_on_demand: float


class CommitmentRecommendation(BaseModel):
    on_demand_discountable_monthly_cost: float
    options: list[CommitmentTermOption]
    recommended_term_years: int  # 0 = stay on-demand
    recommendation_reason: str
    currency: str


class CommitmentRequest(BaseModel):
    requirement: CustomerRequirement
    workload_stability: WorkloadStability = WorkloadStability.STEADY
    force: bool = False


# -- Cost forecasting ---------------------------------------------------

class CostForecastPoint(BaseModel):
    month_index: int
    projected_monthly_cost: float
    cumulative_cost: float


class CostForecast(BaseModel):
    starting_monthly_cost: float
    monthly_growth_percent: float
    months: int
    points: list[CostForecastPoint]
    total_projected_cost: float
    currency: str
    methodology_note: str


class ForecastRequest(BaseModel):
    requirement: CustomerRequirement
    monthly_growth_percent: float = 0.0
    months: int = Field(default=12, gt=0, le=60)
    force: bool = False
    commitment_term_years: int = 0


# -- Carbon footprint ---------------------------------------------------

class CarbonEstimate(BaseModel):
    region: str
    estimated_vcpu_hours_per_month: float
    grid_carbon_intensity_gco2e_per_kwh: float
    estimated_kwh_per_month: float
    estimated_kgco2e_per_month: float
    methodology_note: str


class CarbonRequest(BaseModel):
    requirement: CustomerRequirement
    force: bool = False


# -- Region / scenario comparison ----------------------------------------

class RegionCostOption(BaseModel):
    region: str
    total_monthly: float
    currency: str


class RegionComparisonRequest(BaseModel):
    requirement: CustomerRequirement
    regions: list[str] = Field(min_length=1)
    force: bool = True


class RegionComparison(BaseModel):
    options: list[RegionCostOption]
    cheapest_region: str
    most_expensive_region: str
    max_savings_monthly: float
    currency: str


class ScenarioRequest(BaseModel):
    name: str
    # A shallow patch merged over `base` (as a dict) before pricing - e.g.
    # {"region": "europe-west1"} or {"compute": {"machine_family": "n2"}}.
    # Nested dicts are merged one level deep per top-level key, which
    # covers every realistic scenario (swap a whole section, or tweak the
    # top-level region/strategy) without needing a full JSON-patch engine.
    overrides: dict[str, Any] = Field(default_factory=dict)


class ScenarioComparisonRequest(BaseModel):
    base: CustomerRequirement
    scenarios: list[ScenarioRequest] = Field(min_length=1)
    force: bool = False
    commitment_term_years: int = 0


class ScenarioOutcome(BaseModel):
    name: str
    total_monthly: float
    total_yearly: float
    currency: str
    delta_vs_base_monthly: float
    delta_vs_base_percent: float


class ScenarioComparison(BaseModel):
    base: ScenarioOutcome
    scenarios: list[ScenarioOutcome]


# -- Cross-cloud comparison (Phase 9) --------------------------------------

class CloudCostOption(BaseModel):
    cloud_provider: str  # "gcp" | "aws" | "azure"
    total_monthly: float
    currency: str
    primary_machine_type: str | None = None


class CloudComparisonRequest(BaseModel):
    requirement: CustomerRequirement
    clouds: list[str] = Field(default_factory=lambda: ["gcp", "aws", "azure"], min_length=1)
    force: bool = True


class CloudComparison(BaseModel):
    options: list[CloudCostOption]
    cheapest_cloud: str
    most_expensive_cloud: str
    max_savings_monthly: float
    currency: str


# -- Budget tracking ------------------------------------------------------

class BudgetStatus(BaseModel):
    budget_monthly: float | None
    actual_monthly: float
    within_budget: bool | None  # None when no budget is set on the project
    overage_amount: float | None
    overage_percent: float | None


# -- Historical version comparison (extends Phase 3 project versioning) ----

class VersionComparison(BaseModel):
    from_version: int
    to_version: int
    from_total_monthly: float
    to_total_monthly: float
    delta_monthly: float
    delta_percent: float
    currency: str
    category_deltas: dict[str, float]
