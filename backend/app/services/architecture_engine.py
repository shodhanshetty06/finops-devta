"""
ArchitectureEngine: produces a recommended layered architecture (frontend,
backend, database, networking, storage, load balancer, monitoring, security,
backup, disaster recovery) from the normalized spec and original request.
Rule-based and deterministic - not a pricing source, purely descriptive.
"""
from app.domain.architecture import ArchitectureComponent, ArchitectureRecommendation
from app.domain.estimate import NormalizedSpec
from app.domain.requirements import CustomerRequirement


class ArchitectureEngine:
    def generate(self, requirement: CustomerRequirement, spec: NormalizedSpec) -> ArchitectureRecommendation:
        components: list[ArchitectureComponent] = []

        if spec.kubernetes_node_count is not None or (requirement.kubernetes and requirement.kubernetes.required):
            mode = "Autopilot" if (requirement.kubernetes and requirement.kubernetes.autopilot) else "Standard"
            components.append(ArchitectureComponent(
                layer="Backend",
                service=f"Google Kubernetes Engine ({mode})",
                rationale="Containerized workload orchestration with managed scaling and upgrades.",
            ))
        elif spec.machine_type:
            components.append(ArchitectureComponent(
                layer="Backend",
                service=f"Compute Engine ({spec.machine_type} x {spec.instance_count})",
                rationale="Directly sized VM instances matching the requested/normalized compute profile.",
            ))

        if spec.database_tier:
            ha_note = " with High Availability (regional failover)" if (requirement.database and requirement.database.high_availability) else ""
            components.append(ArchitectureComponent(
                layer="Database",
                service=f"Cloud SQL ({requirement.database.engine.value}, {spec.database_tier}){ha_note}",
                rationale="Fully managed relational database matching the requested engine and sizing.",
            ))

        catalog_service_ids = {s.service_id for s in requirement.selected_services}
        if spec.load_balancer or "load-balancing" in catalog_service_ids:
            components.append(ArchitectureComponent(
                layer="Load Balancer",
                service="External HTTP(S) Load Balancer",
                rationale="Distributes traffic across backend instances/nodes and terminates TLS.",
            ))
            components.append(ArchitectureComponent(
                layer="Security",
                service="Cloud Armor",
                rationale="WAF and DDoS protection at the load balancer edge, recommended whenever a public LB is present.",
            ))

        if (requirement.network and requirement.network.cdn_enabled) or "cloud-cdn" in catalog_service_ids:
            components.append(ArchitectureComponent(
                layer="Networking",
                service="Cloud CDN",
                rationale="Edge caching for static/cacheable content to reduce latency and origin load.",
            ))

        if spec.disk_type:
            components.append(ArchitectureComponent(
                layer="Storage",
                service=f"Persistent Disk ({spec.disk_type})",
                rationale="Block storage attached to compute instances.",
            ))

        if requirement.storage and requirement.storage.snapshot_enabled:
            components.append(ArchitectureComponent(
                layer="Backup",
                service="Scheduled Persistent Disk Snapshots",
                rationale=f"Automated snapshots with {requirement.storage.snapshot_retention_days}-day retention.",
            ))

        if requirement.availability:
            a = requirement.availability
            if a.disaster_recovery_required:
                components.append(ArchitectureComponent(
                    layer="Disaster Recovery",
                    service="Multi-region backup replication",
                    rationale="Cross-region snapshot/backup replication to support recovery objectives.",
                ))
            if a.high_availability:
                components.append(ArchitectureComponent(
                    layer="Networking",
                    service="Multi-zone deployment",
                    rationale="Spreads instances across zones within the region to survive a single-zone outage.",
                ))

        # Baseline components present in every recommendation.
        components.append(ArchitectureComponent(
            layer="Monitoring",
            service="Cloud Monitoring + Cloud Logging",
            rationale="Standard observability stack for metrics, uptime checks, and centralized logs.",
        ))
        components.append(ArchitectureComponent(
            layer="Security",
            service="IAM least-privilege roles + Secret Manager",
            rationale="Baseline access control and secrets management for any production workload.",
        ))

        summary = (
            f"Recommended architecture for '{requirement.project_name}' in {spec.region}: "
            f"{len(components)} components spanning "
            f"{', '.join(sorted({c.layer for c in components}))}."
        )
        return ArchitectureRecommendation(summary=summary, components=components)
