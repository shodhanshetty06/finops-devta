"""Assumption logging - the platform must never silently change a customer's
requested configuration. Every substitution made by the normalization engine
is recorded as an Assumption and surfaced everywhere (Excel, PDF, API, audit log)."""
import re

from pydantic import BaseModel

# Plain-English labels for the field codes normalization/recommendation/intake
# code actually emits (see app/normalization/engine.py, app/services/
# recommendation_engine.py, app/intake/text_extractor.py) - "compute.vcpu"
# means nothing to a customer reading a cost report; "CPU count" does.
_FIELD_LABELS: dict[str, str] = {
    "region": "Region",
    "compute": "Compute (server) sizing",
    "compute.vcpu": "CPU count (vCPUs)",
    "compute.ram_gb": "Memory (RAM)",
    "compute.machine_family": "Machine family",
    "compute.gpu_type": "GPU type",
    "compute.gpu_count": "GPU count",
    "storage.disk_type": "Disk type",
    "storage.size_gb": "Disk size",
    "database": "Database",
    "database.tier": "Database tier",
    "database.size_gb": "Database storage size",
    "database.high_availability": "Database high availability",
    "kubernetes": "Kubernetes",
    "kubernetes.required": "Kubernetes",
    "kubernetes.node_count": "Number of Kubernetes nodes",
    "network.load_balancer_required": "Load balancer",
    "network.estimated_egress_gb_per_month": "Estimated monthly data transfer out",
    "network.cdn_enabled": "CDN",
    "business.total_users": "Total users",
    "business.peak_concurrent_users": "Peak concurrent users",
    "availability.target_uptime_percent": "Uptime target",
    "availability.high_availability": "High availability",
    "availability.disaster_recovery_required": "Disaster recovery",
}


def humanize_field_code(field: str) -> str:
    """Plain-English label for a dotted field code - Assumption.field
    (e.g. "compute.vcpu") and ValidationResult.field both use the same
    "category.subfield" convention, so this is shared by both. Always
    available, no external dependencies. Falls back to turning any unmapped
    code (e.g. "storage.additional_disks[0].disk_type") into a readable
    label by stripping array indices, taking the last dotted segment, and
    title-casing it, so a field this platform adds later still renders
    sensibly without needing an update to _FIELD_LABELS above."""
    label = _FIELD_LABELS.get(field)
    if label:
        return label
    cleaned = re.sub(r"\[\d+\]", "", field)
    last_segment = cleaned.split(".")[-1]
    return last_segment.replace("_", " ").strip().capitalize()


class Assumption(BaseModel):
    field: str
    requested_value: str
    used_value: str
    reason: str
    strategy_applied: str | None = None
