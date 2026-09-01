"""
NormalizationEngine: turns an (possibly invalid) CustomerRequirement into a
NormalizedSpec that maps 1:1 onto real, purchasable Google Cloud resources,
recording every substitution as an Assumption. Pricing and reporting layers
operate exclusively on the NormalizedSpec - never on the raw request - so
that a customer's typo or unrealistic ask can never silently flow into a
priced estimate without an explanation attached.
"""
from app.catalog.base import CatalogProvider
from app.catalog.models import MachineFamilyCapability
from app.core.config import NormalizationStrategy
from app.core.constants import HOURS_PER_MONTH
from app.domain.assumption import Assumption
from app.domain.enums import MachineTypeKind
from app.domain.estimate import NormalizedDisk, NormalizedSpec
from app.domain.requirements import CustomerRequirement
from app.normalization.strategy import select_value

# Used only when exactly one of hours_per_day/days_per_month is set, to fill
# in the other side of the multiplication - matches HOURS_PER_MONTH / 24.
_DEFAULT_DAYS_PER_MONTH = HOURS_PER_MONTH / 24  # ~30.42
_DEFAULT_HOURS_PER_DAY = 24.0


class NormalizationEngine:
    def normalize(
        self,
        requirement: CustomerRequirement,
        catalog: CatalogProvider,
        strategy: NormalizationStrategy,
    ) -> tuple[NormalizedSpec, list[Assumption]]:
        assumptions: list[Assumption] = []

        region = self._normalize_region(requirement, catalog, assumptions)

        machine_type = family = vcpu = ram_gb = instance_count = machine_type_kind = None
        gpu_type = None
        gpu_count = 0
        provisioning_model = operating_system = running_hours_per_month = None
        if requirement.compute is not None:
            machine_type, family, vcpu, ram_gb, machine_type_kind = self._normalize_compute(requirement, catalog, strategy, assumptions)
            instance_count = requirement.compute.instance_count
            gpu_type = requirement.compute.gpu_type.value if requirement.compute.gpu_type.value != "none" else None
            gpu_count = requirement.compute.gpu_count
            provisioning_model = requirement.compute.provisioning_model.value
            operating_system = requirement.compute.operating_system.value
            running_hours_per_month = self._normalize_running_hours(requirement)

        disk_type = disk_size_gb = None
        additional_disks: list[NormalizedDisk] = []
        local_ssd_count = 0
        if requirement.storage is not None:
            disk_type, disk_size_gb = self._normalize_storage(requirement, catalog, assumptions)
            additional_disks = self._normalize_additional_disks(requirement, catalog, assumptions)
            local_ssd_count = requirement.storage.local_ssd_count

        database_tier = database_size_gb = None
        if requirement.database is not None and requirement.database.required:
            database_tier, database_size_gb = self._normalize_database(requirement, catalog, strategy, assumptions)

        k8s_nodes = None
        if requirement.kubernetes is not None and requirement.kubernetes.required:
            k8s_nodes = self._normalize_kubernetes(requirement, catalog, assumptions)

        load_balancer = bool(requirement.network and requirement.network.load_balancer_required)
        static_ip_count = requirement.network.external_ip_count if requirement.network else 0

        spec = NormalizedSpec(
            region=region,
            machine_type=machine_type,
            family=family,
            machine_type_kind=machine_type_kind,
            vcpu=vcpu,
            ram_gb=ram_gb,
            instance_count=instance_count,
            provisioning_model=provisioning_model,
            operating_system=operating_system,
            running_hours_per_month=running_hours_per_month,
            disk_type=disk_type,
            disk_size_gb=disk_size_gb,
            additional_disks=additional_disks,
            local_ssd_count=local_ssd_count,
            gpu_type=gpu_type,
            gpu_count=gpu_count,
            database_tier=database_tier,
            database_size_gb=database_size_gb,
            kubernetes_node_count=k8s_nodes,
            load_balancer=load_balancer,
            static_ip_count=static_ip_count,
        )
        return spec, assumptions

    def _normalize_running_hours(self, requirement: CustomerRequirement) -> float | None:
        c = requirement.compute
        if c.hours_per_day is None and c.days_per_month is None:
            return None  # 24/7 - PricingEngine falls back to the standard full-month constant
        hours_per_day = c.hours_per_day if c.hours_per_day is not None else _DEFAULT_HOURS_PER_DAY
        days_per_month = c.days_per_month if c.days_per_month is not None else _DEFAULT_DAYS_PER_MONTH
        return round(min(hours_per_day * days_per_month, HOURS_PER_MONTH), 2)

    # -- individual normalizers -------------------------------------------------

    def _normalize_region(self, requirement, catalog: CatalogProvider, assumptions: list[Assumption]) -> str:
        region = requirement.region.value
        if catalog.is_region_supported(region):
            return region
        regions = catalog.list_regions()
        fallback = regions[0].code if regions else "us-central1"
        assumptions.append(Assumption(
            field="region",
            requested_value=region,
            used_value=fallback,
            reason=f"'{region}' is not a supported region; defaulted to '{fallback}'.",
        ))
        return fallback

    def _normalize_compute(self, requirement, catalog: CatalogProvider, strategy, assumptions: list[Assumption]):
        """Returns (machine_type_name, family, vcpu, ram_gb, machine_type_kind).

        Three ways a ComputeRequirement resolves, checked in order:
          1. `machine_type` given -> that predefined type's own vcpu/ram/family
             wins outright (see ComputeRequirement's docstring).
          2. `machine_type_kind == "custom"` (and no `machine_type`) -> price
             the exact requested vcpu/ram_gb, after checking the family's
             MachineFamilyCapability. Validation (CustomMachineTypeValidationRule)
             already blocks an unsupported/out-of-range request before this
             ever runs, unless the caller passed force=True - in that case
             this clamps into range rather than silently mispricing.
          3. Neither given -> this platform's historical behavior: resolve to
             an exact predefined match, or snap to the nearest one per the
             configured NormalizationStrategy.
        """
        c = requirement.compute
        family = c.machine_family.value

        if c.machine_type:
            spec = catalog.get_machine_type(c.machine_type)
            if spec is not None:
                if spec.family != family:
                    assumptions.append(Assumption(
                        field="compute.machine_family",
                        requested_value=family,
                        used_value=spec.family,
                        reason=f"'{c.machine_type}' belongs to the '{spec.family}' family, not the declared '{family}'; the machine type's own family was used.",
                        strategy_applied=strategy.value,
                    ))
                return spec.name, spec.family, spec.vcpu, spec.ram_gb, "predefined"

            assumptions.append(Assumption(
                field="compute.machine_type",
                requested_value=c.machine_type,
                used_value="(sized from vCPU/RAM instead)" if c.vcpu else "(defaulted to the smallest type in the family)",
                reason=f"'{c.machine_type}' is not a recognized predefined Compute Engine machine type.",
                strategy_applied=strategy.value,
            ))
            if c.vcpu is None or c.ram_gb is None:
                fallback = min(catalog.list_machine_types(family=family), key=lambda m: m.vcpu, default=None)
                if fallback is not None:
                    return fallback.name, fallback.family, fallback.vcpu, fallback.ram_gb, "predefined"
                return c.machine_type, family, 1, 1.0, "predefined"
            # else: fall through to the vcpu/ram-based resolution below.

        if c.machine_type_kind == MachineTypeKind.CUSTOM and not c.machine_type:
            return self._normalize_custom_compute(c, family, catalog, strategy, assumptions)

        machine_types = catalog.list_machine_types(family=family)

        exact = [m for m in machine_types if m.vcpu == c.vcpu and abs(m.ram_gb - c.ram_gb) < 1e-6]
        if exact:
            m = exact[0]
            return m.name, m.family, m.vcpu, m.ram_gb, "predefined"

        vcpu_options = [m.vcpu for m in machine_types]
        selected_vcpu, vcpu_reason = select_value(c.vcpu, vcpu_options, strategy)

        # Among machine types with the selected vCPU, choose the RAM closest to requested.
        candidates = [m for m in machine_types if m.vcpu == selected_vcpu]
        chosen = min(candidates, key=lambda m: abs(m.ram_gb - c.ram_gb))

        if chosen.vcpu != c.vcpu:
            assumptions.append(Assumption(
                field="compute.vcpu",
                requested_value=str(c.vcpu),
                used_value=str(chosen.vcpu),
                reason=f"{c.vcpu} vCPU configuration does not exist in the {family} family. Selected {vcpu_reason}.",
                strategy_applied=strategy.value,
            ))
        if abs(chosen.ram_gb - c.ram_gb) > 1e-6:
            assumptions.append(Assumption(
                field="compute.ram_gb",
                requested_value=str(c.ram_gb),
                used_value=str(chosen.ram_gb),
                reason=f"RAM is fixed per machine type in the {family} family; '{chosen.name}' provides {chosen.ram_gb} GB.",
                strategy_applied=strategy.value,
            ))
        return chosen.name, chosen.family, chosen.vcpu, chosen.ram_gb, "predefined"

    def _normalize_custom_compute(self, c, family: str, catalog: CatalogProvider, strategy, assumptions: list[Assumption]):
        cap = catalog.get_family_capability(family)
        if cap is not None and cap.supports_custom:
            vcpu, ram_gb = self._clamp_custom_shape(c.vcpu, c.ram_gb, cap)
            if vcpu != c.vcpu:
                assumptions.append(Assumption(
                    field="compute.vcpu",
                    requested_value=str(c.vcpu), used_value=str(vcpu),
                    reason=f"{c.vcpu} vCPU is outside the '{family}' family's supported custom range/increment; clamped to {vcpu}.",
                    strategy_applied=strategy.value,
                ))
            if abs(ram_gb - c.ram_gb) > 1e-6:
                assumptions.append(Assumption(
                    field="compute.ram_gb",
                    requested_value=str(c.ram_gb), used_value=str(ram_gb),
                    reason=f"{c.ram_gb} GB RAM is outside the '{family}' family's supported custom RAM-per-vCPU range/increment; clamped to {ram_gb} GB.",
                    strategy_applied=strategy.value,
                ))
            name = f"{family}-custom-{vcpu}-{int(round(ram_gb * 1024))}"
            return name, family, vcpu, ram_gb, "custom"

        # The family doesn't support custom configurations at all.
        # CustomMachineTypeValidationRule already turns this into a BLOCKER
        # that halts the pipeline before normalization ever runs, unless the
        # caller explicitly passed force=True - only reachable that way.
        machine_types = catalog.list_machine_types(family=family)
        if machine_types:
            chosen = min(machine_types, key=lambda m: (abs(m.vcpu - c.vcpu), abs(m.ram_gb - c.ram_gb)))
            assumptions.append(Assumption(
                field="compute.machine_type_kind",
                requested_value=f"custom ({c.vcpu} vCPU / {c.ram_gb} GB)",
                used_value=chosen.name,
                reason=f"The '{family}' family does not support custom machine configurations; priced the closest predefined type instead (force=true was set).",
                strategy_applied=strategy.value,
            ))
            return chosen.name, chosen.family, chosen.vcpu, chosen.ram_gb, "predefined"

        assumptions.append(Assumption(
            field="compute.machine_type_kind",
            requested_value="custom",
            used_value=f"{c.vcpu} vCPU / {c.ram_gb} GB (unvalidated)",
            reason=f"The '{family}' family does not support custom configurations and has no predefined types either; pricing the requested shape as-is because force=true was set.",
            strategy_applied=strategy.value,
        ))
        return f"{family}-custom-{c.vcpu}-{int(round(c.ram_gb * 1024))}", family, c.vcpu, c.ram_gb, "custom"

    @staticmethod
    def _clamp_custom_shape(vcpu: int, ram_gb: float, cap: MachineFamilyCapability) -> tuple[int, float]:
        lo_vcpu = cap.min_vcpu or 1
        hi_vcpu = cap.max_vcpu or vcpu
        clamped_vcpu = min(max(vcpu, lo_vcpu), hi_vcpu)
        step = cap.vcpu_step or 1
        if step > 1 and clamped_vcpu != 1:
            stepped = round(clamped_vcpu / step) * step
            clamped_vcpu = min(max(stepped, lo_vcpu if lo_vcpu != 1 else step), hi_vcpu)

        ratio = ram_gb / vcpu if vcpu else 0.0
        lo_ratio = cap.min_ram_gb_per_vcpu if cap.min_ram_gb_per_vcpu is not None else 0.0
        hi_ratio = cap.max_ram_gb_per_vcpu if cap.max_ram_gb_per_vcpu is not None else float("inf")
        clamped_ratio = min(max(ratio, lo_ratio), hi_ratio)
        increment = cap.ram_increment_gb or 0.25
        raw_ram = clamped_vcpu * clamped_ratio
        clamped_ram = round(round(raw_ram / increment) * increment, 2)
        return int(clamped_vcpu), clamped_ram

    def _normalize_storage(self, requirement, catalog: CatalogProvider, assumptions: list[Assumption]):
        s = requirement.storage
        return self._normalize_disk(s.disk_type.value, s.size_gb, catalog, assumptions, field_prefix="storage")

    def _normalize_additional_disks(self, requirement, catalog: CatalogProvider, assumptions: list[Assumption]) -> list[NormalizedDisk]:
        result: list[NormalizedDisk] = []
        for i, disk in enumerate(requirement.storage.additional_disks):
            name, size = self._normalize_disk(
                disk.disk_type.value, disk.size_gb, catalog, assumptions,
                field_prefix=f"storage.additional_disks[{i}]",
            )
            result.append(NormalizedDisk(disk_type=name, size_gb=size))
        return result

    def _normalize_disk(self, disk_type_value: str, size_gb: int, catalog: CatalogProvider, assumptions: list[Assumption], field_prefix: str):
        disk_specs = {d.name: d for d in catalog.list_disk_types()}
        spec = disk_specs.get(disk_type_value)
        if spec is None:
            # Fall back to the safest general-purpose disk type.
            fallback_name = "pd-balanced" if "pd-balanced" in disk_specs else next(iter(disk_specs))
            assumptions.append(Assumption(
                field=f"{field_prefix}.disk_type",
                requested_value=disk_type_value,
                used_value=fallback_name,
                reason=f"'{disk_type_value}' is not a recognized disk type; defaulted to '{fallback_name}'.",
            ))
            spec = disk_specs[fallback_name]

        size = size_gb
        if size < spec.min_size_gb or size > spec.max_size_gb:
            clamped = min(max(size, spec.min_size_gb), spec.max_size_gb)
            assumptions.append(Assumption(
                field=f"{field_prefix}.size_gb",
                requested_value=str(size),
                used_value=str(clamped),
                reason=f"Requested size is outside the valid range for '{spec.name}' ({spec.min_size_gb}-{spec.max_size_gb} GB).",
            ))
            size = clamped
        return spec.name, size

    def _normalize_database(self, requirement, catalog: CatalogProvider, strategy, assumptions: list[Assumption]):
        db = requirement.database
        tiers = catalog.list_cloud_sql_tiers(engine=db.engine.value)
        if not tiers:
            tiers = catalog.list_cloud_sql_tiers()

        if db.machine_tier == "shared-core":
            # Shared-core (Google's db-f1-micro, AWS's db.t3.micro, ...) is a
            # flat, provider-published SKU, not a vCPU/RAM shape to size -
            # vcpu/ram_gb are ignored. Picking the catalog's own smallest
            # tier (rather than hardcoding a GCP-specific name) keeps this
            # correct for AWS/Azure catalogs too.
            smallest = min(tiers, key=lambda t: (t.vcpu, t.ram_gb))
            return smallest.tier, db.size_gb

        exact = [t for t in tiers if t.vcpu == db.vcpu and abs(t.ram_gb - db.ram_gb) < 1e-6]
        if exact:
            chosen = exact[0]
        else:
            vcpu_options = [t.vcpu for t in tiers]
            selected_vcpu, vcpu_reason = select_value(db.vcpu, vcpu_options, strategy)
            candidates = [t for t in tiers if t.vcpu == selected_vcpu]
            chosen = min(candidates, key=lambda t: abs(t.ram_gb - db.ram_gb))
            assumptions.append(Assumption(
                field="database.tier",
                requested_value=f"{db.vcpu} vCPU / {db.ram_gb} GB",
                used_value=f"{chosen.tier} ({chosen.vcpu} vCPU / {chosen.ram_gb} GB)",
                reason=f"No exact Cloud SQL tier match. Selected {vcpu_reason}.",
                strategy_applied=strategy.value,
            ))
        return chosen.tier, db.size_gb

    def _normalize_kubernetes(self, requirement, catalog: CatalogProvider, assumptions: list[Assumption]):
        k = requirement.kubernetes
        if k.autopilot:
            # 0, not None: Autopilot has no static node pool to size, but
            # PricingEngine's `spec.kubernetes_node_count is not None` gate
            # must still fire so the cluster management fee and Autopilot
            # pod-resource pricing get priced - None there means "no
            # Kubernetes was requested at all," which isn't the case here.
            return 0
        gke = catalog.get_gke_config()
        if k.node_count < gke.min_node_count or k.node_count > gke.max_node_count:
            clamped = min(max(k.node_count, gke.min_node_count), gke.max_node_count)
            assumptions.append(Assumption(
                field="kubernetes.node_count",
                requested_value=str(k.node_count),
                used_value=str(clamped),
                reason=f"Node count must be between {gke.min_node_count} and {gke.max_node_count}.",
            ))
            return clamped
        return k.node_count
