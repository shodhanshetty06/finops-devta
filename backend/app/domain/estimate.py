"""Top-level estimate result returned by the API and consumed by the Excel /
PDF generators and dashboard."""
from pydantic import BaseModel, Field

from app.domain.architecture import ArchitectureRecommendation
from app.domain.assumption import Assumption
from app.domain.audit import AuditLog
from app.domain.pricing import CostBreakdown
from app.domain.requirements import CustomerRequirement
from app.domain.validation import ValidationReport


class NormalizedDisk(BaseModel):
    """One normalized additional/data disk (see NormalizedSpec.additional_disks)."""

    disk_type: str
    size_gb: int


class NormalizedSpec(BaseModel):
    """The customer's request after normalization to valid GCP configurations."""

    region: str
    machine_type: str | None = None
    # Canonical compute-tier code (e.g. "e2", "n2") the machine_type was
    # normalized from - PricingEngine looks pricing up by this, not by
    # parsing `machine_type` (Phase 9: that used to assume GCP's hyphenated
    # "family-tier-size" naming convention, which breaks for AWS/Azure
    # instance names like "m5.xlarge" or "Standard_D4s_v5").
    family: str | None = None
    vcpu: int | None = None
    ram_gb: float | None = None
    instance_count: int | None = None

    # On-demand vs. Spot (see app.domain.enums.ProvisioningModel); None means
    # no compute was requested at all (distinct from "on_demand", which is
    # an explicit choice).
    provisioning_model: str | None = None
    # Guest OS/license (see app.domain.enums.OperatingSystem); "linux" and
    # None are both cost-free but kept distinct for the same reason as above.
    operating_system: str | None = None
    # None = full 730-hour billing month (every estimate before this field
    # existed behaves identically); otherwise the customer-specified
    # hours/day x days/month, clamped to a full month.
    running_hours_per_month: float | None = None

    disk_type: str | None = None  # boot disk
    disk_size_gb: int | None = None  # boot disk
    additional_disks: list[NormalizedDisk] = Field(default_factory=list)
    local_ssd_count: int = 0

    gpu_type: str | None = None
    gpu_count: int = 0
    database_tier: str | None = None
    database_size_gb: int | None = None
    kubernetes_node_count: int | None = None
    load_balancer: bool = False
    static_ip_count: int = 0


class EstimateResult(BaseModel):
    estimate_id: str
    project_name: str
    strategy_used: str

    original_request: CustomerRequirement
    normalized_spec: NormalizedSpec
    assumptions: list[Assumption]
    validation: ValidationReport
    architecture: ArchitectureRecommendation
    cost: CostBreakdown
    audit_log: AuditLog
