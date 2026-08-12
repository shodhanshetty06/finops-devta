"""
Input schemas: what a customer or consultant submits, either via questionnaire
form fields or parsed from an uploaded Excel file. These models intentionally
accept "untrusted" values (e.g. cpu=3) - the validation engine is responsible
for judging whether a value is realistic/supported, not this layer.
"""
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import (
    BackupFrequency,
    CloudSqlEngine,
    DiskType,
    GkeEdition,
    GpuType,
    MachineFamily,
    OperatingSystem,
    ProvisioningModel,
    Region,
)


class ComputeRequirement(BaseModel):
    machine_family: MachineFamily = MachineFamily.E2
    vcpu: int = Field(..., gt=0, description="Requested vCPU count, as entered by the customer")
    ram_gb: float = Field(..., gt=0, description="Requested RAM in GB")
    instance_count: int = Field(default=1, gt=0)
    gpu_type: GpuType = GpuType.NONE
    gpu_count: int = Field(default=0, ge=0)

    provisioning_model: ProvisioningModel = ProvisioningModel.ON_DEMAND
    operating_system: OperatingSystem = OperatingSystem.LINUX

    # Running duration: both left unset means "runs 24/7" (the historical
    # default - a full 730-hour billing month), matching every estimate
    # created before this field existed. Setting either one switches the
    # instance to partial-month billing (e.g. an 8-hours/day, 22-days/month
    # dev server) - see NormalizationEngine._normalize_running_hours.
    hours_per_day: float | None = Field(default=None, gt=0, le=24, description="Hours/day the instance runs; omit for 24/7")
    days_per_month: float | None = Field(default=None, gt=0, le=31, description="Days/month the instance runs; omit for every day")

    @field_validator("vcpu")
    @classmethod
    def vcpu_reasonable(cls, v: int) -> int:
        if v > 416:
            raise ValueError("vCPU count exceeds any known Google Cloud machine type (max ~416)")
        return v


class AdditionalDiskRequirement(BaseModel):
    """One secondary/data disk attached to each compute instance, beyond the
    boot disk described by StorageRequirement.disk_type/size_gb."""

    disk_type: DiskType = DiskType.PD_BALANCED
    size_gb: int = Field(..., gt=0)


class StorageRequirement(BaseModel):
    """`disk_type`/`size_gb` describe the boot disk. `additional_disks` are
    extra data disks attached to each instance; `local_ssd_count` is the
    number of fixed-size (375 GB) Local SSD scratch blocks per instance.

    `provisioned_iops`/`provisioned_throughput_mbps` only apply to
    `pd-extreme` (and custom-provisioned SSD) disks - 0 elsewhere.
    `snapshot_storage_gb`, when set, prices snapshot storage directly
    instead of estimating it from `snapshot_retention_days`."""

    disk_type: DiskType = DiskType.PD_BALANCED
    size_gb: int = Field(..., gt=0)
    snapshot_enabled: bool = False
    snapshot_retention_days: int = Field(default=7, ge=0)
    snapshot_storage_gb: float = Field(default=0, ge=0)
    provisioned_iops: int = Field(default=0, ge=0)
    provisioned_throughput_mbps: float = Field(default=0, ge=0)
    additional_disks: list[AdditionalDiskRequirement] = Field(default_factory=list)
    local_ssd_count: int = Field(default=0, ge=0, le=24, description="Number of 375 GB Local SSD blocks per instance (GCP max 24)")


class DatabaseRequirement(BaseModel):
    """`machine_tier="shared-core"` bills a flat db-f1-micro rate and ignores
    `vcpu`/`ram_gb`; `commitment` applies the same Committed Use Discount
    percentages `PricingEngine` already uses for compute, but scoped to this
    instance's own compute spend only (storage/backups are never
    CUD-eligible on real Google Cloud)."""

    required: bool = False
    engine: CloudSqlEngine = CloudSqlEngine.POSTGRES
    machine_tier: str = Field(default="custom", pattern="^(shared-core|custom)$")
    size_gb: int = Field(default=0, ge=0)
    storage_type: str = Field(default="ssd", pattern="^(hdd|ssd)$")
    vcpu: int = Field(default=2, gt=0)
    ram_gb: float = Field(default=8, gt=0)
    high_availability: bool = False
    backup_storage_gb: float = Field(default=0, ge=0)
    binary_log_storage_gb: float = Field(default=0, ge=0)
    commitment: str = Field(default="none", pattern="^(none|1-year|3-year)$")


class NetworkRequirement(BaseModel):
    load_balancer_required: bool = False
    external_ip_count: int = Field(default=0, ge=0)
    estimated_egress_gb_per_month: float = Field(default=0, ge=0)
    estimated_ingress_gb_per_month: float = Field(default=0, ge=0)
    cdn_enabled: bool = False
    vpn_required: bool = False


class KubernetesRequirement(BaseModel):
    """GKE cluster sizing. Standard-mode node pool fields and Autopilot-mode
    pod resource fields both live here (rather than as two separate
    requirement shapes) so flipping `autopilot` just changes which block
    PricingEngine reads - everything defaults to "no usage" (0/None) except
    the handful of fields Pydantic requires to be non-zero (`node_vcpu`/
    `node_ram_gb`/`node_disk_size_gb`/`pod_vcpu`/`pod_memory_gb`/
    `pod_ephemeral_storage_gb`), which default to GKE's own real-world
    minimums so an untouched card still prices a sane single node/pod.

    Persistent volume claims are priced via the "Persistent Disk" catalog
    card (already described as "attached to Compute Engine/GKE instances"),
    and load balancers/egress/Cloud NAT via their own Networking cards -
    deliberately not duplicated here, so each cost dimension is still priced
    in exactly one place."""

    required: bool = False
    autopilot: bool = False
    edition: GkeEdition = GkeEdition.STANDARD
    regional: bool = False
    provisioning_model: ProvisioningModel = ProvisioningModel.ON_DEMAND

    # Standard mode node pool - ignored by PricingEngine when autopilot=True.
    node_count: int = Field(default=0, ge=0, description="Regional clusters replicate this count across 3 zones (see `regional`).")
    machine_family: MachineFamily = MachineFamily.E2
    node_vcpu: int = Field(default=4, gt=0, le=416)
    node_ram_gb: float = Field(default=16, gt=0)
    node_disk_type: DiskType = DiskType.PD_BALANCED
    node_disk_size_gb: int = Field(default=100, gt=0)
    node_gpu_type: GpuType = GpuType.NONE
    node_gpu_count: int = Field(default=0, ge=0)

    # Autopilot mode - average concurrent pod resource requests. Ignored by
    # PricingEngine when autopilot=False.
    avg_pod_count: int = Field(default=0, ge=0)
    pod_vcpu: float = Field(default=0.25, gt=0, description="GKE Autopilot's minimum requestable vCPU per pod.")
    pod_memory_gb: float = Field(default=0.5, gt=0, description="GKE Autopilot's minimum requestable memory per pod.")
    pod_ephemeral_storage_gb: float = Field(default=1, gt=0)

    # Running duration for both modes - both unset means 24/7 (a full
    # 730-hour billing month), same convention as ComputeRequirement.
    hours_per_day: float | None = Field(default=None, gt=0, le=24)
    days_per_month: float | None = Field(default=None, gt=0, le=31)


class AvailabilityRequirement(BaseModel):
    high_availability: bool = False
    target_uptime_percent: float | None = Field(default=None, ge=0, le=100)
    backup_frequency: BackupFrequency = BackupFrequency.NONE
    disaster_recovery_required: bool = False


class BusinessContext(BaseModel):
    """Optional high-level business inputs the AI recommendation engine can use
    to infer infrastructure when the customer hasn't specified resources directly."""

    total_users: int | None = Field(default=None, ge=0)
    peak_concurrent_users: int | None = Field(default=None, ge=0)
    notes: str | None = None


class ServiceSelection(BaseModel):
    """One entry added from the GCP service catalog on the New Estimate page
    (see app/catalog/service_definitions.py). `config` is free-form and
    validated generically against the matching GCPServiceDefinition's
    configuration_schema (app/validation/rules.py::ServiceCatalogConfigValidationRule)
    rather than against a per-service Pydantic model.

    `quantity` is the explicit, user-editable count of identical resources
    this selection represents (e.g. 4 Cloud Run services with the same
    vCPU/memory config) - it is never inferred from the resource name or
    from how many selections happen to share a config; it always comes
    directly from what the user entered, defaulting to 1."""

    service_id: str
    config: dict[str, Any] = Field(default_factory=dict)
    quantity: int = Field(default=1, ge=1, le=100_000)


class CustomerRequirement(BaseModel):
    """The full, un-trusted customer questionnaire submission."""

    project_name: str
    region: Region = Region.US_CENTRAL1
    normalization_strategy: str | None = None  # overrides server default if set

    compute: ComputeRequirement | None = None
    storage: StorageRequirement | None = None
    database: DatabaseRequirement | None = None
    network: NetworkRequirement | None = None
    kubernetes: KubernetesRequirement | None = None
    availability: AvailabilityRequirement | None = None
    business: BusinessContext | None = None

    # Additive, optional (default []): services added via the New Estimate
    # service catalog. Never required for backward compatibility with
    # existing /questionnaire and Excel/text intake submissions.
    selected_services: list[ServiceSelection] = Field(default_factory=list)

    existing_infrastructure_notes: str | None = None
