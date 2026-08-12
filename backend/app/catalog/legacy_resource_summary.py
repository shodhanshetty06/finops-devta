"""Builds ResourceCostSummary rows for the legacy typed-requirement resources
(Compute Engine, Persistent Disk, Cloud SQL, Networking, GKE) - the
counterpart to build_resource_summaries (app/catalog/resource_summary.py),
which covers GCP-service-catalog selections only.

Never recomputes a price: it groups the CostLineItems PricingEngine already
produced for these resources into one auditable row per resource, using a
declarative sku_id-prefix table rather than per-service branching (the
generic Resource -> Quantity -> Unit Cost -> Subtotal system must not
special-case services). Callers must pass only the legacy-derived slice of
`CostBreakdown.line_items` - i.e. with any generic-catalog `extra_line_items`
already excluded - so a catalog selection can never be double-counted here
and in build_resource_summaries; see EstimationService.generate_estimate.
"""
from app.domain.assumption import Assumption
from app.domain.enums import Severity
from app.domain.estimate import NormalizedSpec
from app.domain.pricing import CostLineItem, ResourceCostSummary
from app.domain.requirements import CustomerRequirement
from app.domain.validation import ValidationReport

# (resource_name, category, sku_id prefixes, assumption/validation field prefix)
_GROUPS: list[tuple[str, str, tuple[str, ...], str]] = [
    ("Compute Engine", "Compute", ("compute-", "gpu-", "os-license-", "local-ssd"), "compute."),
    ("Persistent Disk", "Storage", ("disk-", "snapshot-storage"), "storage."),
    ("Cloud SQL", "Database", ("cloudsql-",), "database."),
    ("Networking", "Network", ("network-egress", "load-balancer", "static-ip"), "network."),
    ("GKE", "Compute", ("gke-",), "kubernetes."),
]


def _quantity_for(resource_name: str, spec: NormalizedSpec, requirement: CustomerRequirement) -> int:
    if resource_name in ("Compute Engine", "Persistent Disk"):
        return spec.instance_count or 1
    if resource_name == "GKE":
        if requirement.kubernetes and requirement.kubernetes.autopilot:
            return requirement.kubernetes.avg_pod_count or 1
        return spec.kubernetes_node_count or 1
    return 1


def _status_for(matching_assumptions: list[Assumption], matching_issues: list) -> str:
    if any(v.severity == Severity.BLOCKER for v in matching_issues):
        return "unsupported"
    if matching_assumptions:
        return "normalized"
    if matching_issues:
        return "assumption"
    return "valid"


def _describe(resource_name: str, spec: NormalizedSpec, requirement: CustomerRequirement) -> tuple[str, str]:
    """Returns (requested_configuration, normalized_configuration)."""
    if resource_name == "Compute Engine" and requirement.compute:
        c = requirement.compute
        requested = (
            f"{c.vcpu} vCPU / {c.ram_gb:g} GB RAM, {c.machine_family.value} family, "
            f"{c.instance_count} instance(s)"
        )
        normalized = (
            f"{spec.machine_type}, {spec.vcpu} vCPU / {spec.ram_gb:g} GB RAM, "
            f"{spec.operating_system}, {spec.provisioning_model}, {spec.instance_count} instance(s)"
        )
        return requested, normalized

    if resource_name == "Persistent Disk" and requirement.storage:
        s = requirement.storage
        extra = f" + {len(s.additional_disks)} additional disk(s)" if s.additional_disks else ""
        requested = f"{s.disk_type.value} {s.size_gb} GB boot disk{extra}"
        norm_extra = f" + {len(spec.additional_disks)} additional disk(s)" if spec.additional_disks else ""
        normalized = f"{spec.disk_type} {spec.disk_size_gb} GB boot disk{norm_extra}"
        return requested, normalized

    if resource_name == "Cloud SQL" and requirement.database:
        d = requirement.database
        requested = f"{d.engine.value}, {d.vcpu} vCPU / {d.ram_gb:g} GB RAM, {d.size_gb} GB storage"
        normalized = f"{spec.database_tier}, {spec.database_size_gb} GB storage"
        return requested, normalized

    if resource_name == "Networking" and requirement.network:
        n = requirement.network
        parts = []
        if spec.load_balancer:
            parts.append("Load balancer")
        if spec.static_ip_count:
            parts.append(f"{spec.static_ip_count} static IP(s)")
        if n.estimated_egress_gb_per_month:
            parts.append(f"{n.estimated_egress_gb_per_month:g} GB/mo egress")
        text = ", ".join(parts) or "Networking"
        return text, text

    if resource_name == "GKE" and requirement.kubernetes:
        k = requirement.kubernetes
        mode = "Autopilot" if k.autopilot else "Standard"
        if k.autopilot:
            text = f"GKE {mode}, {k.avg_pod_count} pod(s), {k.pod_vcpu:g} vCPU / {k.pod_memory_gb:g} GB per pod"
            return text, text
        requested = f"GKE {mode}, {k.node_count} node(s) requested, {k.node_vcpu:g} vCPU / {k.node_ram_gb:g} GB per node"
        normalized = f"GKE {mode}, {spec.kubernetes_node_count} node(s), {k.node_vcpu:g} vCPU / {k.node_ram_gb:g} GB per node"
        return requested, normalized

    return "", ""


def build_legacy_resource_summaries(
    legacy_line_items: list[CostLineItem],
    spec: NormalizedSpec,
    requirement: CustomerRequirement,
    assumptions: list[Assumption],
    validation: ValidationReport,
) -> list[ResourceCostSummary]:
    summaries: list[ResourceCostSummary] = []
    for resource_name, category, prefixes, field_prefix in _GROUPS:
        items = [li for li in legacy_line_items if any(li.sku_id.startswith(p) for p in prefixes)]
        if not items:
            continue

        subtotal = round(sum(li.monthly_amount for li in items), 2)
        quantity = _quantity_for(resource_name, spec, requirement)
        # `subtotal` (the sum of real, already-computed line items) is
        # authoritative; unit_cost is derived from it, not the other way
        # around, so it must keep enough precision that unit_cost x quantity
        # reconstructs subtotal exactly rather than drifting a cent off
        # after re-rounding (same 6-decimal precision PricingEngine already
        # uses for hourly unit prices, e.g. engine.py's os_hourly/db_hourly).
        unit_cost = round(subtotal / quantity, 6) if quantity else subtotal

        matching_assumptions = [a for a in assumptions if a.field.startswith(field_prefix)]
        matching_issues = [v for v in validation.results if v.field.startswith(field_prefix) and not v.is_valid]
        requested_cfg, normalized_cfg = _describe(resource_name, spec, requirement)

        summaries.append(ResourceCostSummary(
            resource_name=resource_name,
            configuration=normalized_cfg,
            quantity=quantity,
            unit_cost=unit_cost,
            subtotal=subtotal,
            currency=items[0].currency,
            category=category,
            sku_id=items[0].sku_id if len(items) == 1 else None,
            pricing_source=items[0].source,
            region=spec.region,
            requested_configuration=requested_cfg,
            normalized_configuration=normalized_cfg,
            status=_status_for(matching_assumptions, matching_issues),
            assumption_reason="; ".join(a.reason for a in matching_assumptions) or None,
        ))
    return summaries
