"""
Concrete validation rules.

Every rule returns a ValidationResult per field it inspects, always carrying:
requested value, supported value (best-known valid alternative, may be None),
reason, severity, and a human-readable recommendation. Rules never mutate the
request - that is the normalization engine's job.
"""
from app.catalog.base import CatalogProvider
from app.catalog.service_definitions import SERVICE_CATALOG_BY_ID
from app.domain.enums import MachineTypeKind, Severity
from app.domain.requirements import CustomerRequirement
from app.domain.validation import ValidationResult
from app.validation.base import ValidationRule


def _ok(field: str, rule: str, value: str, reason: str) -> ValidationResult:
    return ValidationResult(
        field=field,
        rule=rule,
        requested_value=value,
        supported_value=value,
        is_valid=True,
        severity=Severity.INFO,
        reason=reason,
        recommendation="No action needed.",
    )


def _uses_legacy_predefined_matching(c) -> bool:
    """True only when NormalizationEngine will run its legacy exact-match-or-
    snap-to-nearest path for this request (see _normalize_compute) - i.e. no
    `machine_type` name was given directly, and no explicit `machine_type_kind`
    (custom or predefined) was set. CpuValidationRule/RamValidationRule/
    MachineFamilyValidationRule below only make sense in that case: a
    directly-named machine_type is checked by MachineTypeValidationRule
    instead, and an explicit custom shape is *expected* to not match any
    predefined vCPU/RAM pairing - that's the point - so it's checked by
    CustomMachineTypeValidationRule instead."""
    return c.machine_type is None and c.machine_type_kind is None and c.vcpu is not None and c.ram_gb is not None


def _effective_family(c, catalog: CatalogProvider) -> str:
    """The family actually being priced: a directly-named `machine_type`'s
    own family wins (see NormalizationEngine._normalize_compute - same
    precedence), falling back to the declared `machine_family` when the
    name isn't recognized (MachineTypeValidationRule already reports that
    separately as its own BLOCKER)."""
    if c.machine_type:
        spec = catalog.get_machine_type(c.machine_type)
        if spec is not None:
            return spec.family
    return c.machine_family.value


class CpuValidationRule(ValidationRule):
    name = "cpu_validation"

    def evaluate(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> list[ValidationResult]:
        if requirement.compute is None or not _uses_legacy_predefined_matching(requirement.compute):
            return []
        c = requirement.compute
        machine_types = catalog.list_machine_types(family=c.machine_family.value)
        valid_vcpus = sorted({m.vcpu for m in machine_types})

        if c.vcpu in valid_vcpus:
            return [_ok("compute.vcpu", self.name, str(c.vcpu),
                         f"{c.vcpu} vCPU is a supported configuration for the {c.machine_family.value} family.")]

        return [ValidationResult(
            field="compute.vcpu",
            rule=self.name,
            requested_value=str(c.vcpu),
            supported_value=None,
            is_valid=False,
            severity=Severity.WARNING,
            reason=(
                f"{c.vcpu} vCPU does not exist as a standard configuration in the "
                f"{c.machine_family.value} family. Valid options: {valid_vcpus}."
            ),
            recommendation="Normalize to the nearest supported vCPU count per the configured strategy.",
        )]


class RamValidationRule(ValidationRule):
    name = "ram_validation"

    def evaluate(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> list[ValidationResult]:
        if requirement.compute is None or not _uses_legacy_predefined_matching(requirement.compute):
            return []
        c = requirement.compute
        machine_types = catalog.list_machine_types(family=c.machine_family.value)
        matching = [m for m in machine_types if abs(m.ram_gb - c.ram_gb) < 1e-6]

        if matching:
            return [_ok("compute.ram_gb", self.name, str(c.ram_gb),
                         f"{c.ram_gb} GB RAM matches a supported machine type in the {c.machine_family.value} family.")]

        valid_ram = sorted({m.ram_gb for m in machine_types})
        return [ValidationResult(
            field="compute.ram_gb",
            rule=self.name,
            requested_value=str(c.ram_gb),
            supported_value=None,
            is_valid=False,
            severity=Severity.WARNING,
            reason=(
                f"{c.ram_gb} GB RAM is not offered as a standalone configuration in the "
                f"{c.machine_family.value} family. Valid RAM values: {valid_ram}."
            ),
            recommendation="Normalize to the RAM amount tied to the nearest supported vCPU/RAM pairing.",
        )]


class MachineFamilyValidationRule(ValidationRule):
    name = "machine_family_validation"

    def evaluate(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> list[ValidationResult]:
        if requirement.compute is None or not _uses_legacy_predefined_matching(requirement.compute):
            return []
        c = requirement.compute
        machine_types = catalog.list_machine_types(family=c.machine_family.value)
        exact_match = any(
            m.vcpu == c.vcpu and abs(m.ram_gb - c.ram_gb) < 1e-6 for m in machine_types
        )
        if exact_match:
            name = next(m.name for m in machine_types if m.vcpu == c.vcpu and abs(m.ram_gb - c.ram_gb) < 1e-6)
            return [_ok("compute.machine_family", self.name, c.machine_family.value,
                         f"Requested vCPU/RAM combination maps directly to machine type '{name}'.")]

        return [ValidationResult(
            field="compute.machine_family",
            rule=self.name,
            requested_value=f"{c.machine_family.value} ({c.vcpu} vCPU / {c.ram_gb} GB)",
            supported_value=None,
            is_valid=False,
            severity=Severity.WARNING,
            reason=(
                f"No exact '{c.machine_family.value}' machine type offers {c.vcpu} vCPU with "
                f"{c.ram_gb} GB RAM together."
            ),
            recommendation=(
                "Normalization engine will select the closest predefined machine type in this "
                "family, or an alternative family if none fits within tolerance."
            ),
        )]


class MachineFamilyRegionValidationRule(ValidationRule):
    """Validates that the effective machine family is actually available in
    the selected region - distinct from CpuValidationRule/RamValidationRule/
    CustomMachineTypeValidationRule above, which only check whether the
    *shape* (vCPU/RAM) is valid for the family, never whether the family
    itself can be ordered in this region at all. Runs unconditionally
    whenever compute + a recognized region are both present - regardless of
    predefined-by-name, custom, or legacy vCPU/RAM sizing - since regional
    availability is a property of the family, not of how vcpu/ram_gb were
    resolved. Never changes the family or region itself; a BLOCKER here
    means the request cannot be priced as asked, not that it should be
    silently substituted."""

    name = "machine_family_region_validation"

    def evaluate(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> list[ValidationResult]:
        if requirement.compute is None:
            return []
        region = requirement.region.value
        if not catalog.is_region_supported(region):
            return []  # RegionValidationRule already reports this as its own BLOCKER

        c = requirement.compute
        family = _effective_family(c, catalog)
        cap = catalog.get_family_capability(family)
        if cap is None or cap.available_regions is None or region in cap.available_regions:
            return [_ok("compute.machine_family", self.name, f"{family} in {region}",
                         f"The '{family}' machine family is available in '{region}'.")]

        return [ValidationResult(
            field="compute.machine_family", rule=self.name,
            requested_value=f"{family} in {region}",
            supported_value=", ".join(cap.available_regions), is_valid=False, severity=Severity.BLOCKER,
            reason=f"The '{family}' machine family is not available in region '{region}'.",
            recommendation=(
                f"Choose a supported region for {family} ({', '.join(cap.available_regions)}), "
                f"or switch to a different machine family available in '{region}'."
            ),
        )]


class MachineTypeValidationRule(ValidationRule):
    """Validates a directly-specified `machine_type` name (e.g.
    "n4-standard-4") against the catalog - a customer choosing a predefined
    machine type by name, rather than a vCPU/RAM shape."""

    name = "machine_type_validation"

    def evaluate(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> list[ValidationResult]:
        if requirement.compute is None or not requirement.compute.machine_type:
            return []
        c = requirement.compute
        spec = catalog.get_machine_type(c.machine_type)
        if spec is None:
            known = sorted({m.name for m in catalog.list_machine_types(family=c.machine_family.value)})
            return [ValidationResult(
                field="compute.machine_type", rule=self.name, requested_value=c.machine_type,
                supported_value=", ".join(known) or None, is_valid=False, severity=Severity.BLOCKER,
                reason=f"'{c.machine_type}' is not a recognized predefined Compute Engine machine type.",
                recommendation=(
                    f"Choose one of the {c.machine_family.value} family's predefined types "
                    f"({', '.join(known)}), or set machine_type_kind='custom' with vcpu/ram_gb instead."
                    if known else "Set machine_type_kind='custom' with vcpu/ram_gb instead."
                ),
            )]
        if spec.family != c.machine_family.value:
            return [ValidationResult(
                field="compute.machine_type", rule=self.name,
                requested_value=f"{c.machine_type} (declared family: {c.machine_family.value})",
                supported_value=spec.family, is_valid=True, severity=Severity.WARNING,
                reason=f"'{c.machine_type}' actually belongs to the '{spec.family}' family, not the declared '{c.machine_family.value}'.",
                recommendation=f"The machine type's own family ('{spec.family}') will be used for pricing.",
            )]
        return [_ok("compute.machine_type", self.name, c.machine_type,
                     f"'{c.machine_type}' is a recognized predefined machine type ({spec.vcpu} vCPU / {spec.ram_gb} GB).")]


class CustomMachineTypeValidationRule(ValidationRule):
    """Validates an explicit custom vCPU/RAM request against the family's
    MachineFamilyCapability BEFORE it reaches pricing - never assume every
    family accepts an arbitrary custom shape (e.g. T2D/T2A/C2/A2/N4A/C4A
    don't support custom machine types at all on real Google Cloud)."""

    name = "custom_machine_type_validation"

    def evaluate(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> list[ValidationResult]:
        if requirement.compute is None:
            return []
        c = requirement.compute
        if c.machine_type or c.machine_type_kind != MachineTypeKind.CUSTOM:
            return []
        if c.vcpu is None or c.ram_gb is None:
            return []  # already rejected by ComputeRequirement's own model validator

        family = c.machine_family.value
        cap = catalog.get_family_capability(family)
        if cap is None or not cap.supports_custom:
            supported = sorted(f.family for f in catalog.list_family_capabilities() if f.supports_custom)
            return [ValidationResult(
                field="compute.machine_type_kind", rule=self.name,
                requested_value=f"custom ({family}, {c.vcpu} vCPU / {c.ram_gb} GB)",
                supported_value=", ".join(supported) or None, is_valid=False, severity=Severity.BLOCKER,
                reason=f"The '{family}' machine family does not support custom vCPU/RAM configurations.",
                recommendation=(
                    f"Choose a predefined {family} machine type instead, or switch to a family that "
                    f"supports custom configurations: {', '.join(supported)}." if supported else
                    f"Choose a predefined {family} machine type instead."
                ),
            )]

        issues: list[str] = []
        if cap.min_vcpu is not None and c.vcpu < cap.min_vcpu:
            issues.append(f"vCPU must be >= {cap.min_vcpu} for {family} custom instances (got {c.vcpu}).")
        elif cap.max_vcpu is not None and c.vcpu > cap.max_vcpu:
            issues.append(f"vCPU must be <= {cap.max_vcpu} for {family} custom instances (got {c.vcpu}).")
        elif cap.vcpu_step > 1 and c.vcpu != 1 and c.vcpu % cap.vcpu_step != 0:
            issues.append(f"vCPU count must be a multiple of {cap.vcpu_step} for {family} custom instances (got {c.vcpu}).")

        ram_per_vcpu = c.ram_gb / c.vcpu
        if cap.min_ram_gb_per_vcpu is not None and ram_per_vcpu < cap.min_ram_gb_per_vcpu - 1e-9:
            issues.append(f"RAM per vCPU ({ram_per_vcpu:.3g} GB) is below the {family} minimum of {cap.min_ram_gb_per_vcpu} GB/vCPU.")
        if cap.max_ram_gb_per_vcpu is not None and ram_per_vcpu > cap.max_ram_gb_per_vcpu + 1e-9:
            issues.append(f"RAM per vCPU ({ram_per_vcpu:.3g} GB) exceeds the {family} maximum of {cap.max_ram_gb_per_vcpu} GB/vCPU.")
        increment = cap.ram_increment_gb or 0.25
        nearest = round(c.ram_gb / increment) * increment
        if abs(nearest - c.ram_gb) > 1e-6:
            issues.append(f"RAM must be a multiple of {increment} GB for {family} custom instances (got {c.ram_gb} GB).")

        if issues:
            return [ValidationResult(
                field="compute.machine_type_kind", rule=self.name,
                requested_value=f"custom ({family}, {c.vcpu} vCPU / {c.ram_gb} GB)",
                supported_value=None, is_valid=False, severity=Severity.BLOCKER,
                reason=" ".join(issues),
                recommendation="Adjust vCPU/RAM to a supported custom shape for this family, or pass force=true to price the nearest valid shape instead.",
            )]
        return [_ok("compute.machine_type_kind", self.name, f"custom ({family}, {c.vcpu} vCPU / {c.ram_gb} GB)",
                     f"Custom {family} configuration is within the family's supported vCPU/RAM range.")]


class GpuValidationRule(ValidationRule):
    name = "gpu_validation"

    def evaluate(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> list[ValidationResult]:
        if requirement.compute is None or requirement.compute.gpu_type.value == "none":
            return []
        c = requirement.compute
        gpu_specs = {g.name: g for g in catalog.list_gpu_types()}
        gpu = gpu_specs.get(c.gpu_type.value)

        if gpu is None:
            return [ValidationResult(
                field="compute.gpu_type",
                rule=self.name,
                requested_value=c.gpu_type.value,
                supported_value=", ".join(gpu_specs.keys()),
                is_valid=False,
                severity=Severity.BLOCKER,
                reason=f"GPU type '{c.gpu_type.value}' is not a recognized Google Cloud accelerator.",
                recommendation=f"Choose one of: {', '.join(gpu_specs.keys())}.",
            )]

        results = []
        if c.machine_family.value not in gpu.compatible_families:
            results.append(ValidationResult(
                field="compute.gpu_type",
                rule=self.name,
                requested_value=f"{c.gpu_type.value} on {c.machine_family.value}",
                supported_value=", ".join(gpu.compatible_families),
                is_valid=False,
                severity=Severity.BLOCKER,
                reason=(
                    f"GPU '{c.gpu_type.value}' cannot be attached to the '{c.machine_family.value}' "
                    f"machine family. Compatible families: {gpu.compatible_families}."
                ),
                recommendation=f"Switch machine family to one of: {gpu.compatible_families}.",
            ))
        if c.gpu_count > gpu.max_per_instance:
            results.append(ValidationResult(
                field="compute.gpu_count",
                rule=self.name,
                requested_value=str(c.gpu_count),
                supported_value=str(gpu.max_per_instance),
                is_valid=False,
                severity=Severity.WARNING,
                reason=f"Requested {c.gpu_count} GPUs exceeds the max of {gpu.max_per_instance} per instance for {c.gpu_type.value}.",
                recommendation=f"Cap GPU count at {gpu.max_per_instance} per instance, or scale out with more instances.",
            ))
        if not results:
            results.append(_ok("compute.gpu_type", self.name, c.gpu_type.value,
                                "GPU type and count are compatible with the requested machine family."))
        return results


class RegionValidationRule(ValidationRule):
    name = "region_validation"

    def evaluate(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> list[ValidationResult]:
        region = requirement.region.value
        if catalog.is_region_supported(region):
            return [_ok("region", self.name, region, f"'{region}' is a supported Google Cloud region.")]
        supported = [r.code for r in catalog.list_regions()]
        return [ValidationResult(
            field="region",
            rule=self.name,
            requested_value=region,
            supported_value=supported[0] if supported else None,
            is_valid=False,
            severity=Severity.BLOCKER,
            reason=f"'{region}' is not a supported region in the catalog. Supported: {supported}.",
            recommendation=f"Choose a supported region, e.g. '{supported[0] if supported else 'us-central1'}'.",
        )]


class DiskValidationRule(ValidationRule):
    name = "disk_validation"

    def evaluate(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> list[ValidationResult]:
        if requirement.storage is None:
            return []
        s = requirement.storage
        disk_specs = {d.name: d for d in catalog.list_disk_types()}
        spec = disk_specs.get(s.disk_type.value)
        if spec is None:
            return [ValidationResult(
                field="storage.disk_type", rule=self.name, requested_value=s.disk_type.value,
                supported_value=", ".join(disk_specs.keys()), is_valid=False, severity=Severity.BLOCKER,
                reason=f"Disk type '{s.disk_type.value}' is not recognized.",
                recommendation=f"Choose one of: {', '.join(disk_specs.keys())}.",
            )]

        results = []
        if s.size_gb < spec.min_size_gb or s.size_gb > spec.max_size_gb:
            clamped = min(max(s.size_gb, spec.min_size_gb), spec.max_size_gb)
            results.append(ValidationResult(
                field="storage.size_gb", rule=self.name, requested_value=str(s.size_gb),
                supported_value=str(clamped), is_valid=False, severity=Severity.WARNING,
                reason=(
                    f"{s.size_gb} GB is outside the allowed range for '{s.disk_type.value}' "
                    f"({spec.min_size_gb}-{spec.max_size_gb} GB)."
                ),
                recommendation=f"Clamp requested size to {clamped} GB.",
            ))
        else:
            results.append(_ok("storage.size_gb", self.name, str(s.size_gb),
                                f"{s.size_gb} GB is within the valid range for '{s.disk_type.value}'."))
        return results


class CloudStorageValidationRule(ValidationRule):
    """Validates object-storage-style usage patterns implied by snapshot/backup
    configuration (distinct from block Persistent Disk validation above)."""

    name = "cloud_storage_validation"

    def evaluate(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> list[ValidationResult]:
        if requirement.storage is None or not requirement.storage.snapshot_enabled:
            return []
        s = requirement.storage
        if s.snapshot_retention_days > 365:
            return [ValidationResult(
                field="storage.snapshot_retention_days", rule=self.name,
                requested_value=str(s.snapshot_retention_days), supported_value="365",
                is_valid=False, severity=Severity.WARNING,
                reason="Snapshot retention beyond 365 days is unusual and significantly increases Cloud Storage cost.",
                recommendation="Cap retention at 365 days unless there is a compliance requirement for longer retention.",
            )]
        return [_ok("storage.snapshot_retention_days", self.name, str(s.snapshot_retention_days),
                     "Snapshot retention period is within a typical operational range.")]


class CloudSqlValidationRule(ValidationRule):
    name = "cloud_sql_tier_validation"

    def evaluate(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> list[ValidationResult]:
        if requirement.database is None or not requirement.database.required:
            return []
        db = requirement.database
        tiers = catalog.list_cloud_sql_tiers(engine=db.engine.value)
        if not tiers:
            return [ValidationResult(
                field="database.engine", rule=self.name, requested_value=db.engine.value,
                supported_value=None, is_valid=False, severity=Severity.BLOCKER,
                reason=f"No Cloud SQL tiers support engine '{db.engine.value}'.",
                recommendation="Choose a supported engine: postgres, mysql, or sqlserver.",
            )]
        exact = [t for t in tiers if t.vcpu == db.vcpu and abs(t.ram_gb - db.ram_gb) < 1e-6]
        if exact:
            return [_ok("database.vcpu_ram", self.name, f"{db.vcpu} vCPU / {db.ram_gb} GB",
                         f"Matches Cloud SQL tier '{exact[0].tier}'.")]
        valid_combos = [f"{t.vcpu}vCPU/{t.ram_gb}GB ({t.tier})" for t in tiers]
        return [ValidationResult(
            field="database.vcpu_ram", rule=self.name,
            requested_value=f"{db.vcpu} vCPU / {db.ram_gb} GB",
            supported_value=None, is_valid=False, severity=Severity.WARNING,
            reason=f"No Cloud SQL tier exactly matches {db.vcpu} vCPU / {db.ram_gb} GB. Available: {valid_combos}.",
            recommendation="Normalize to the nearest available Cloud SQL tier per the configured strategy.",
        )]


class LoadBalancerValidationRule(ValidationRule):
    name = "load_balancer_validation"

    def evaluate(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> list[ValidationResult]:
        if requirement.network is None:
            return []
        n = requirement.network
        if n.cdn_enabled and not n.load_balancer_required:
            return [ValidationResult(
                field="network.cdn_enabled", rule=self.name, requested_value="true",
                supported_value="load_balancer_required=true", is_valid=False, severity=Severity.WARNING,
                reason="Cloud CDN requires a Google Cloud external HTTP(S) Load Balancer as its origin.",
                recommendation="Enable load_balancer_required alongside cdn_enabled.",
            )]
        if n.load_balancer_required and n.external_ip_count < 1:
            return [ValidationResult(
                field="network.external_ip_count", rule=self.name, requested_value=str(n.external_ip_count),
                supported_value="1", is_valid=False, severity=Severity.WARNING,
                reason="A load balancer requires at least one external (or global anycast) IP address.",
                recommendation="Set external_ip_count to at least 1.",
            )]
        return [_ok("network.load_balancer", self.name, str(n.load_balancer_required),
                     "Load balancer / CDN configuration is internally consistent.")]


class NetworkValidationRule(ValidationRule):
    name = "network_validation"

    def evaluate(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> list[ValidationResult]:
        if requirement.network is None:
            return []
        n = requirement.network
        results = []
        threshold_gb = 200_000
        if n.estimated_egress_gb_per_month > threshold_gb:
            results.append(ValidationResult(
                field="network.estimated_egress_gb_per_month", rule=self.name,
                requested_value=str(n.estimated_egress_gb_per_month), supported_value=str(threshold_gb),
                is_valid=True, severity=Severity.WARNING,
                reason=(
                    f"{n.estimated_egress_gb_per_month:,.0f} GB/month egress is very high; "
                    "standard internet egress pricing may not be cost-optimal at this volume."
                ),
                recommendation="Evaluate Cloud Interconnect or a Committed Use Network Discount for sustained high egress.",
            ))
        else:
            results.append(_ok("network.estimated_egress_gb_per_month", self.name,
                                str(n.estimated_egress_gb_per_month), "Egress volume is within typical ranges."))
        return results


class KubernetesValidationRule(ValidationRule):
    name = "kubernetes_validation"

    def evaluate(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> list[ValidationResult]:
        if requirement.kubernetes is None or not requirement.kubernetes.required:
            return []
        k = requirement.kubernetes
        gke = catalog.get_gke_config()

        if k.autopilot and not gke.autopilot_available:
            return [ValidationResult(
                field="kubernetes.autopilot", rule=self.name, requested_value="true",
                supported_value="false", is_valid=False, severity=Severity.BLOCKER,
                reason="GKE Autopilot is not available in this catalog configuration.",
                recommendation="Use GKE Standard mode instead.",
            )]

        if not k.autopilot and (k.node_count < gke.min_node_count or k.node_count > gke.max_node_count):
            clamped = min(max(k.node_count, gke.min_node_count), gke.max_node_count)
            return [ValidationResult(
                field="kubernetes.node_count", rule=self.name, requested_value=str(k.node_count),
                supported_value=str(clamped), is_valid=False, severity=Severity.WARNING,
                reason=f"Node count must be between {gke.min_node_count} and {gke.max_node_count}.",
                recommendation=f"Clamp node count to {clamped}.",
            )]
        return [_ok("kubernetes.node_count", self.name, str(k.node_count if not k.autopilot else "autopilot-managed"),
                     "Kubernetes configuration is valid.")]


class AvailabilityValidationRule(ValidationRule):
    name = "availability_validation"

    def evaluate(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> list[ValidationResult]:
        if requirement.availability is None:
            return []
        a = requirement.availability
        results = []
        if a.target_uptime_percent is not None:
            if a.target_uptime_percent > 99.99:
                results.append(ValidationResult(
                    field="availability.target_uptime_percent", rule=self.name,
                    requested_value=str(a.target_uptime_percent), supported_value="99.99",
                    is_valid=False, severity=Severity.WARNING,
                    reason="Requested uptime exceeds Google Cloud's highest published managed-service SLA (99.99%).",
                    recommendation="Target 99.99% with multi-region HA and automated failover, and document remaining risk in the proposal.",
                ))
            elif a.target_uptime_percent >= 99.95 and not a.high_availability:
                results.append(ValidationResult(
                    field="availability.high_availability", rule=self.name,
                    requested_value="false", supported_value="true",
                    is_valid=False, severity=Severity.WARNING,
                    reason=f"{a.target_uptime_percent}% uptime is not realistically achievable without HA enabled.",
                    recommendation="Enable high_availability to support the requested uptime target.",
                ))
            else:
                results.append(_ok("availability.target_uptime_percent", self.name,
                                    str(a.target_uptime_percent), "Uptime target is achievable with the requested configuration."))
        return results


class BackupValidationRule(ValidationRule):
    name = "backup_validation"

    def evaluate(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> list[ValidationResult]:
        if requirement.availability is None:
            return []
        a = requirement.availability
        results = []
        if a.disaster_recovery_required and a.backup_frequency.value == "none":
            results.append(ValidationResult(
                field="availability.backup_frequency", rule=self.name, requested_value="none",
                supported_value="daily", is_valid=False, severity=Severity.WARNING,
                reason="Disaster recovery was requested but no backup frequency is configured.",
                recommendation="Set backup_frequency to at least 'daily' to support disaster recovery objectives.",
            ))
        else:
            results.append(_ok("availability.backup_frequency", self.name, a.backup_frequency.value,
                                "Backup configuration is consistent with stated recovery requirements."))
        return results


class ServiceCatalogConfigValidationRule(ValidationRule):
    """The one generic rule covering every service in the GCP service
    catalog (app/catalog/service_definitions.py) - driven entirely by each
    service's `configuration_schema` (required/min_value/max_value/options),
    never by a per-service branch. Never raises a BLOCKER: an unknown or
    out-of-range catalog selection should surface as a warning, not halt an
    estimate that also has legacy-section requirements."""

    name = "service_catalog_config_validation"

    def evaluate(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for selection in requirement.selected_services:
            field = f"selected_services.{selection.service_id}"
            definition = SERVICE_CATALOG_BY_ID.get(selection.service_id)
            if definition is None or not definition.active:
                results.append(ValidationResult(
                    field=field, rule=self.name, requested_value=selection.service_id,
                    supported_value=None, is_valid=False, severity=Severity.WARNING,
                    reason=f"'{selection.service_id}' is not a known active service in the GCP service catalog.",
                    recommendation="Remove this selection or pick a currently supported service.",
                ))
                continue

            issues: list[str] = []
            for config_field in definition.configuration_schema:
                value = selection.config.get(config_field.field_id, config_field.default)
                if config_field.required and value is None:
                    issues.append(f"'{config_field.label}' is required")
                    continue
                if value is None:
                    continue
                if config_field.field_type == "number":
                    try:
                        numeric_value = float(value)
                    except (TypeError, ValueError):
                        issues.append(f"'{config_field.label}' must be a number")
                        continue
                    if config_field.min_value is not None and numeric_value < config_field.min_value:
                        issues.append(f"'{config_field.label}' must be >= {config_field.min_value}")
                    if config_field.max_value is not None and numeric_value > config_field.max_value:
                        issues.append(f"'{config_field.label}' must be <= {config_field.max_value}")
                elif config_field.field_type == "select" and config_field.options:
                    valid_values = {opt.value for opt in config_field.options}
                    if value not in valid_values:
                        issues.append(f"'{config_field.label}' must be one of {sorted(valid_values)}")

            if issues:
                results.append(ValidationResult(
                    field=field, rule=self.name, requested_value=str(selection.config),
                    supported_value=None, is_valid=False, severity=Severity.WARNING,
                    reason=f"{definition.display_name} configuration issue(s): {'; '.join(issues)}.",
                    recommendation="Update the service configuration to satisfy the listed constraints.",
                ))
            else:
                results.append(_ok(field, self.name, definition.display_name,
                                    f"{definition.display_name} configuration is valid."))
        return results


ALL_RULES: list[ValidationRule] = [
    CpuValidationRule(),
    RamValidationRule(),
    MachineFamilyValidationRule(),
    MachineFamilyRegionValidationRule(),
    MachineTypeValidationRule(),
    CustomMachineTypeValidationRule(),
    GpuValidationRule(),
    RegionValidationRule(),
    DiskValidationRule(),
    CloudStorageValidationRule(),
    CloudSqlValidationRule(),
    LoadBalancerValidationRule(),
    NetworkValidationRule(),
    KubernetesValidationRule(),
    AvailabilityValidationRule(),
    BackupValidationRule(),
    ServiceCatalogConfigValidationRule(),
]
