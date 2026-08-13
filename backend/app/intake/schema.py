"""
Single source of truth describing every field a customer questionnaire can
capture. Both `excel_template.py` (writes the blank workbook customers fill
in) and `excel_parser.py` (reads a filled-in workbook back) are driven by
this same list, so the template and the parser can never silently drift out
of sync with each other or with `app.domain.requirements.CustomerRequirement`.
"""
from dataclasses import dataclass, field

from app.domain.enums import (
    BackupFrequency,
    CloudSqlEngine,
    DiskType,
    GpuType,
    MachineFamily,
    Region,
)


@dataclass(frozen=True)
class FieldSpec:
    section: str                 # display section / group heading
    label: str                   # exact text in column A - matched case-insensitively on parse
    path: tuple[str, ...]        # nested key path into the CustomerRequirement dict
    value_type: str              # "str" | "int" | "float" | "bool" | "enum"
    choices: list[str] | None = field(default=None)
    example: str = ""            # shown in the template's "Example / Notes" column
    required_if_section_used: bool = False


TOP_LEVEL_SECTION = "Project Info"

FIELD_SCHEMA: list[FieldSpec] = [
    # -- Project Info ---------------------------------------------------------
    FieldSpec(TOP_LEVEL_SECTION, "Project Name", ("project_name",), "str",
              example="e.g. Retail Inventory API - leave blank for a quick, unnamed estimate"),
    FieldSpec(TOP_LEVEL_SECTION, "Region", ("region",), "enum",
              choices=[r.value for r in Region], example="us-central1"),
    FieldSpec(TOP_LEVEL_SECTION, "Normalization Strategy", ("normalization_strategy",), "enum",
              choices=["conservative", "balanced", "performance"],
              example="Leave blank to use the platform default (balanced)"),
    FieldSpec(TOP_LEVEL_SECTION, "Existing Infrastructure Notes", ("existing_infrastructure_notes",), "str",
              example="Free text - anything already running that this should replace or integrate with"),

    # -- Compute (leave entirely blank if you only know business requirements) --
    FieldSpec("Compute", "Machine Family", ("compute", "machine_family"), "enum",
              choices=[f.value for f in MachineFamily], example="e2"),
    FieldSpec("Compute", "vCPU", ("compute", "vcpu"), "int", example="4", required_if_section_used=True),
    FieldSpec("Compute", "RAM (GB)", ("compute", "ram_gb"), "float", example="16", required_if_section_used=True),
    FieldSpec("Compute", "Instance Count", ("compute", "instance_count"), "int", example="2 (default 1)"),
    FieldSpec("Compute", "GPU Type", ("compute", "gpu_type"), "enum",
              choices=[g.value for g in GpuType], example="none"),
    FieldSpec("Compute", "GPU Count", ("compute", "gpu_count"), "int", example="0"),

    # -- Storage --------------------------------------------------------------
    FieldSpec("Storage", "Disk Type", ("storage", "disk_type"), "enum",
              choices=[d.value for d in DiskType], example="pd-balanced"),
    FieldSpec("Storage", "Size (GB)", ("storage", "size_gb"), "int", example="100", required_if_section_used=True),
    FieldSpec("Storage", "Snapshot Enabled", ("storage", "snapshot_enabled"), "bool", example="TRUE or FALSE"),
    FieldSpec("Storage", "Snapshot Retention (Days)", ("storage", "snapshot_retention_days"), "int", example="7"),

    # -- Database ---------------------------------------------------------------
    # Note: labels here are prefixed with "Database" where the field name
    # would otherwise collide with a Compute/Kubernetes/Availability field of
    # the same name (e.g. "vCPU") - every label in this sheet must be
    # globally unique since the parser matches by label text, not by which
    # section a row visually sits under.
    FieldSpec("Database", "Database Required", ("database", "required"), "bool", example="TRUE or FALSE"),
    FieldSpec("Database", "Engine", ("database", "engine"), "enum",
              choices=[e.value for e in CloudSqlEngine], example="postgres"),
    FieldSpec("Database", "Database Size (GB)", ("database", "size_gb"), "int", example="100"),
    FieldSpec("Database", "Database vCPU", ("database", "vcpu"), "int", example="2"),
    FieldSpec("Database", "Database RAM (GB)", ("database", "ram_gb"), "float", example="8"),
    FieldSpec("Database", "Database High Availability", ("database", "high_availability"), "bool", example="TRUE or FALSE"),

    # -- Networking --------------------------------------------------------------
    FieldSpec("Networking", "Load Balancer Required", ("network", "load_balancer_required"), "bool", example="TRUE or FALSE"),
    FieldSpec("Networking", "External IP Count", ("network", "external_ip_count"), "int", example="1"),
    FieldSpec("Networking", "Estimated Egress (GB/month)", ("network", "estimated_egress_gb_per_month"), "float", example="500"),
    FieldSpec("Networking", "Estimated Ingress (GB/month)", ("network", "estimated_ingress_gb_per_month"), "float", example="0"),
    FieldSpec("Networking", "CDN Enabled", ("network", "cdn_enabled"), "bool", example="TRUE or FALSE"),
    FieldSpec("Networking", "VPN Required", ("network", "vpn_required"), "bool", example="TRUE or FALSE"),

    # -- Kubernetes --------------------------------------------------------------
    FieldSpec("Kubernetes", "Kubernetes Required", ("kubernetes", "required"), "bool", example="TRUE or FALSE"),
    FieldSpec("Kubernetes", "Node Count", ("kubernetes", "node_count"), "int", example="3 (leave 0 for Autopilot)"),
    FieldSpec("Kubernetes", "Autopilot", ("kubernetes", "autopilot"), "bool", example="TRUE or FALSE"),

    # -- Availability --------------------------------------------------------------
    FieldSpec("Availability", "High Availability", ("availability", "high_availability"), "bool", example="TRUE or FALSE"),
    FieldSpec("Availability", "Target Uptime (%)", ("availability", "target_uptime_percent"), "float", example="99.95"),
    FieldSpec("Availability", "Backup Frequency", ("availability", "backup_frequency"), "enum",
              choices=[b.value for b in BackupFrequency], example="daily"),
    FieldSpec("Availability", "Disaster Recovery Required", ("availability", "disaster_recovery_required"), "bool", example="TRUE or FALSE"),

    # -- Business Context (fill this INSTEAD of Compute if you only know business needs) --
    FieldSpec("Business Context", "Total Users", ("business", "total_users"), "int", example="500"),
    FieldSpec("Business Context", "Peak Concurrent Users", ("business", "peak_concurrent_users"), "int", example="500"),
    FieldSpec("Business Context", "Notes", ("business", "notes"), "str", example="Any other context for the AI recommendation engine"),
]

SECTION_ORDER = [
    TOP_LEVEL_SECTION, "Compute", "Storage", "Database", "Networking",
    "Kubernetes", "Availability", "Business Context",
]

# Sections whose fields nest under CustomerRequirement.<section_key>; the
# top-level section's fields sit directly on CustomerRequirement itself.
SECTION_KEYS = {
    "Compute": "compute", "Storage": "storage", "Database": "database",
    "Networking": "network", "Kubernetes": "kubernetes",
    "Availability": "availability", "Business Context": "business",
}
