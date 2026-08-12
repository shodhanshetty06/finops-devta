"""
PricingEngine: the ONLY place in the platform that turns resource quantities
into dollar amounts. It always delegates unit prices to a PricingProvider
(never hardcodes a number itself) and returns a fully itemized CostBreakdown
suitable for the API, Excel export, PDF export, and dashboard.
"""
from app.core.config import Settings
from app.core.constants import HOURS_PER_MONTH
from app.domain.enums import GpuType, ProvisioningModel
from app.domain.estimate import NormalizedSpec
from app.domain.pricing import CostBreakdown, CostLineItem, DiscountLineItem
from app.domain.requirements import CustomerRequirement
from app.pricing.base import PricingProvider

# sku_id prefix shared by every GKE Standard node pool line item that is
# eligible for its own Spot/CUD/SUD discount bucket (see the discount
# section below) - kept separate from Compute Engine's own compute/GPU
# spend since a GKE node pool has its own, independent provisioning model.
_GKE_NODE_POOL_SKUS = {"gke-node-pool-compute", "gke-node-pool-gpu"}

# Used only when exactly one of hours_per_day/days_per_month is set on a
# KubernetesRequirement, to fill in the other side of the multiplication -
# mirrors NormalizationEngine._normalize_running_hours for ComputeRequirement.
_DEFAULT_DAYS_PER_MONTH = HOURS_PER_MONTH / 24  # ~30.42
_DEFAULT_HOURS_PER_DAY = 24.0


def _gke_effective_hours(hours_per_day: float | None, days_per_month: float | None) -> float:
    if hours_per_day is None and days_per_month is None:
        return HOURS_PER_MONTH
    h = hours_per_day if hours_per_day is not None else _DEFAULT_HOURS_PER_DAY
    d = days_per_month if days_per_month is not None else _DEFAULT_DAYS_PER_MONTH
    return round(min(h * d, HOURS_PER_MONTH), 2)


class PricingEngine:
    def calculate(
        self,
        spec: NormalizedSpec,
        requirement: CustomerRequirement,
        provider: PricingProvider,
        settings: Settings,
        commitment_term_years: int = 0,
        extra_line_items: list[CostLineItem] | None = None,
    ) -> CostBreakdown:
        line_items: list[CostLineItem] = []
        # Declared here (rather than just before the Compute/GPU/GKE
        # discount buckets below) so the Cloud SQL block can append its own
        # per-instance Committed Use Discount directly - Cloud SQL's
        # `commitment` is a selection on that resource's own card, not the
        # request-wide `commitment_term_years` the Compute/GKE buckets use.
        discounts: list[DiscountLineItem] = []
        currency = provider.get_currency()

        # None = the instance runs 24/7 (a full 730-hour billing month) -
        # every estimate created before running_hours_per_month existed
        # behaves identically. A customer-specified partial-month duration
        # (e.g. an 8-hours/day dev server) only ever reduces compute/GPU/OS-
        # license spend, never disk/network costs, matching how Google
        # actually bills those (storage and reserved IPs are charged whether
        # or not the instance is running).
        effective_hours = spec.running_hours_per_month if spec.running_hours_per_month is not None else HOURS_PER_MONTH
        is_spot = spec.provisioning_model == "spot"
        # GKE's own provisioning model, independent of Compute Engine's -
        # a Standard node pool or an Autopilot cluster can run Spot even
        # when the primary Compute Engine sizing above is on-demand (or
        # vice versa).
        is_gke_spot = bool(requirement.kubernetes and requirement.kubernetes.provisioning_model == ProvisioningModel.SPOT)

        if spec.machine_type and spec.vcpu and spec.ram_gb and spec.instance_count:
            # `spec.family` is the canonical compute-tier code the machine
            # type was normalized from (e.g. "e2", "n2") - looking pricing up
            # by this, rather than parsing `machine_type`, is what makes this
            # engine work unmodified across GCP/AWS/Azure naming conventions
            # (Phase 9). Falls back to parsing machine_type for any spec that
            # predates the `family` field (e.g. a Phase 1-8 saved estimate
            # reloaded from the database without a migration backfill).
            family = spec.family or spec.machine_type.split("-")[0]
            hourly = provider.get_compute_hourly_price_for_spec(spec.vcpu, spec.ram_gb, family, spec.region)
            monthly = hourly * effective_hours * spec.instance_count
            spot_note = " (Spot)" if is_spot else ""
            line_items.append(CostLineItem(
                category="Compute",
                description=f"{spec.machine_type}{spot_note} x {spec.instance_count} instance(s) ({spec.region})",
                sku_id=f"compute-{spec.machine_type}",
                unit="hour",
                quantity=effective_hours * spec.instance_count,
                unit_price=hourly,
                currency=currency,
                monthly_amount=round(monthly, 2),
                source=provider.source_name,
            ))

            if spec.gpu_type and spec.gpu_count:
                gpu_hourly = provider.get_gpu_hourly_price(spec.gpu_type, spec.region)
                gpu_monthly = gpu_hourly * effective_hours * spec.gpu_count * spec.instance_count
                line_items.append(CostLineItem(
                    category="GPU",
                    description=f"{spec.gpu_type} x {spec.gpu_count} per instance, {spec.instance_count} instance(s)",
                    sku_id=f"gpu-{spec.gpu_type}",
                    unit="hour",
                    quantity=effective_hours * spec.gpu_count * spec.instance_count,
                    unit_price=gpu_hourly,
                    currency=currency,
                    monthly_amount=round(gpu_monthly, 2),
                    source=provider.source_name,
                ))

            if spec.operating_system and spec.operating_system != "linux":
                os_hourly = provider.get_os_license_hourly_price(spec.operating_system, spec.vcpu)
                if os_hourly > 0:
                    os_monthly = os_hourly * effective_hours * spec.instance_count
                    line_items.append(CostLineItem(
                        category="Licensing",
                        description=f"{spec.operating_system} license x {spec.instance_count} instance(s)",
                        sku_id=f"os-license-{spec.operating_system}",
                        unit="hour",
                        quantity=effective_hours * spec.instance_count,
                        unit_price=round(os_hourly, 6),
                        currency=currency,
                        monthly_amount=round(os_monthly, 2),
                        source=provider.source_name,
                    ))

            if spec.local_ssd_count > 0:
                ssd_monthly_per_disk = provider.get_local_ssd_monthly_price_per_disk(spec.region)
                ssd_total = ssd_monthly_per_disk * spec.local_ssd_count * spec.instance_count
                line_items.append(CostLineItem(
                    category="Storage",
                    description=f"Local SSD {spec.local_ssd_count} x 375 GB block(s) x {spec.instance_count} instance(s) ({spec.region})",
                    sku_id="local-ssd",
                    unit="GB-month",
                    quantity=spec.local_ssd_count * 375 * spec.instance_count,
                    unit_price=round(ssd_monthly_per_disk / 375, 6),
                    currency=currency,
                    monthly_amount=round(ssd_total, 2),
                    source=provider.source_name,
                ))

        if spec.disk_type and spec.disk_size_gb:
            disk_price = provider.get_disk_monthly_price_per_gb(spec.disk_type, spec.region)
            disk_count = spec.instance_count or 1
            disk_monthly = disk_price * spec.disk_size_gb * disk_count
            line_items.append(CostLineItem(
                category="Storage",
                description=f"{spec.disk_type} {spec.disk_size_gb} GB x {disk_count} disk(s) ({spec.region})",
                sku_id=f"disk-{spec.disk_type}",
                unit="GB-month",
                quantity=spec.disk_size_gb * disk_count,
                unit_price=disk_price,
                currency=currency,
                monthly_amount=round(disk_monthly, 2),
                source=provider.source_name,
            ))

            if requirement.storage and requirement.storage.snapshot_enabled:
                snap_price = provider.get_snapshot_monthly_price_per_gb(spec.region)
                # A direct snapshot_storage_gb input (if the customer entered
                # one) is more accurate than estimating it from retention
                # days x disk size, so it takes priority when set.
                snap_gb = requirement.storage.snapshot_storage_gb or (spec.disk_size_gb * disk_count)
                snap_monthly = snap_price * snap_gb
                line_items.append(CostLineItem(
                    category="Storage",
                    description=f"Persistent disk snapshots, {requirement.storage.snapshot_retention_days}-day retention",
                    sku_id="snapshot-storage",
                    unit="GB-month",
                    quantity=snap_gb,
                    unit_price=snap_price,
                    currency=currency,
                    monthly_amount=round(snap_monthly, 2),
                    source=provider.source_name,
                ))

            if requirement.storage and requirement.storage.provisioned_iops > 0:
                iops_price = provider.get_disk_provisioned_iops_monthly_price_per_iops(spec.region)
                iops_monthly = iops_price * requirement.storage.provisioned_iops * disk_count
                line_items.append(CostLineItem(
                    category="Storage",
                    description=f"Provisioned IOPS: {requirement.storage.provisioned_iops:,.0f} x {disk_count} disk(s) ({spec.region})",
                    sku_id="disk-provisioned-iops",
                    unit="IOPS-month",
                    quantity=requirement.storage.provisioned_iops * disk_count,
                    unit_price=iops_price,
                    currency=currency,
                    monthly_amount=round(iops_monthly, 2),
                    source=provider.source_name,
                ))

            if requirement.storage and requirement.storage.provisioned_throughput_mbps > 0:
                throughput_price = provider.get_disk_provisioned_throughput_monthly_price_per_mbps(spec.region)
                throughput_monthly = throughput_price * requirement.storage.provisioned_throughput_mbps * disk_count
                line_items.append(CostLineItem(
                    category="Storage",
                    description=f"Provisioned throughput: {requirement.storage.provisioned_throughput_mbps:,.0f} MB/s x {disk_count} disk(s) ({spec.region})",
                    sku_id="disk-provisioned-throughput",
                    unit="MB/s-month",
                    quantity=requirement.storage.provisioned_throughput_mbps * disk_count,
                    unit_price=throughput_price,
                    currency=currency,
                    monthly_amount=round(throughput_monthly, 2),
                    source=provider.source_name,
                ))

            for i, extra_disk in enumerate(spec.additional_disks):
                extra_price = provider.get_disk_monthly_price_per_gb(extra_disk.disk_type, spec.region)
                extra_monthly = extra_price * extra_disk.size_gb * disk_count
                line_items.append(CostLineItem(
                    category="Storage",
                    description=f"Additional disk {i + 1}: {extra_disk.disk_type} {extra_disk.size_gb} GB x {disk_count} instance(s) ({spec.region})",
                    sku_id=f"disk-{extra_disk.disk_type}",
                    unit="GB-month",
                    quantity=extra_disk.size_gb * disk_count,
                    unit_price=extra_price,
                    currency=currency,
                    monthly_amount=round(extra_monthly, 2),
                    source=provider.source_name,
                ))

        if spec.database_tier and spec.database_size_gb is not None:
            db_hourly = provider.get_cloud_sql_hourly_price(spec.database_tier, spec.region)
            ha_multiplier = 1.0
            if requirement.database and requirement.database.high_availability:
                ha_multiplier = provider.get_cloud_sql_ha_multiplier()
            db_monthly = db_hourly * HOURS_PER_MONTH * ha_multiplier
            ha_note = " (High Availability - synchronous standby)" if ha_multiplier > 1.0 else ""
            line_items.append(CostLineItem(
                category="Database",
                description=f"Cloud SQL {spec.database_tier}{ha_note} ({spec.region})",
                sku_id=f"cloudsql-{spec.database_tier}",
                unit="hour",
                quantity=HOURS_PER_MONTH,
                unit_price=round(db_hourly * ha_multiplier, 6),
                currency=currency,
                monthly_amount=round(db_monthly, 2),
                source=provider.source_name,
            ))

            # Cloud SQL's own commitment selection (a per-instance card
            # field) is independent of the request-wide
            # commitment_term_years used for Compute Engine/GKE below - a
            # customer can commit their database spend without committing
            # their VM fleet, or vice versa. Never eligible for Spot (Cloud
            # SQL has no Spot/preemptible tier), and only ever discounts the
            # compute line item above, matching real Google Cloud CUD scope
            # (storage/backups are never CUD-eligible).
            commitment_years = {"1-year": 1, "3-year": 3}.get(
                requirement.database.commitment if requirement.database else "none", 0,
            )
            if commitment_years > 0:
                cud_percent = provider.get_committed_use_discount_percent(commitment_years)
                if cud_percent > 0:
                    discounts.append(DiscountLineItem(
                        name=f"{commitment_years}-Year Committed Use Discount (Cloud SQL)",
                        description="Applied to this Cloud SQL instance's compute cost in exchange for a spend commitment.",
                        percent_off=cud_percent,
                        monthly_savings=round(db_monthly * cud_percent / 100, 2),
                    ))

            if spec.database_size_gb > 0:
                db_storage_price = provider.get_cloud_sql_storage_monthly_price_per_gb(spec.region)
                storage_type = requirement.database.storage_type if requirement.database else "ssd"
                db_storage_price *= provider.get_cloud_sql_storage_type_multiplier(storage_type)
                db_storage_monthly = db_storage_price * spec.database_size_gb
                line_items.append(CostLineItem(
                    category="Database",
                    description=f"Cloud SQL storage ({storage_type.upper()}) {spec.database_size_gb} GB ({spec.region})",
                    sku_id="cloudsql-storage",
                    unit="GB-month",
                    quantity=spec.database_size_gb,
                    unit_price=round(db_storage_price, 6),
                    currency=currency,
                    monthly_amount=round(db_storage_monthly, 2),
                    source=provider.source_name,
                ))

            if requirement.database and requirement.database.backup_storage_gb > 0:
                backup_price = provider.get_cloud_sql_backup_storage_monthly_price_per_gb(spec.region)
                backup_monthly = backup_price * requirement.database.backup_storage_gb
                line_items.append(CostLineItem(
                    category="Database",
                    description=f"Cloud SQL backup storage {requirement.database.backup_storage_gb:,.0f} GB ({spec.region})",
                    sku_id="cloudsql-backup-storage",
                    unit="GB-month",
                    quantity=requirement.database.backup_storage_gb,
                    unit_price=backup_price,
                    currency=currency,
                    monthly_amount=round(backup_monthly, 2),
                    source=provider.source_name,
                ))

            if requirement.database and requirement.database.binary_log_storage_gb > 0:
                binlog_price = provider.get_cloud_sql_backup_storage_monthly_price_per_gb(spec.region)
                binlog_monthly = binlog_price * requirement.database.binary_log_storage_gb
                line_items.append(CostLineItem(
                    category="Database",
                    description=f"Cloud SQL binary log storage {requirement.database.binary_log_storage_gb:,.0f} GB ({spec.region})",
                    sku_id="cloudsql-binlog-storage",
                    unit="GB-month",
                    quantity=requirement.database.binary_log_storage_gb,
                    unit_price=binlog_price,
                    currency=currency,
                    monthly_amount=round(binlog_monthly, 2),
                    source=provider.source_name,
                ))

        if requirement.network:
            n = requirement.network
            if n.estimated_egress_gb_per_month > 0:
                egress_price = provider.get_network_egress_price_per_gb(spec.region)
                egress_monthly = egress_price * n.estimated_egress_gb_per_month
                line_items.append(CostLineItem(
                    category="Network",
                    description=f"Internet egress, {n.estimated_egress_gb_per_month:,.0f} GB/month",
                    sku_id="network-egress",
                    unit="GB",
                    quantity=n.estimated_egress_gb_per_month,
                    unit_price=egress_price,
                    currency=currency,
                    monthly_amount=round(egress_monthly, 2),
                    source=provider.source_name,
                ))
            if spec.load_balancer:
                lb_monthly = provider.get_load_balancer_monthly_base_price(spec.region)
                line_items.append(CostLineItem(
                    category="Network",
                    description=f"External HTTP(S) Load Balancer ({spec.region})",
                    sku_id="load-balancer",
                    unit="month",
                    quantity=1,
                    unit_price=lb_monthly,
                    currency=currency,
                    monthly_amount=round(lb_monthly, 2),
                    source=provider.source_name,
                ))

        if spec.static_ip_count > 0:
            ip_monthly = provider.get_static_ip_monthly_price(spec.region)
            ip_total = ip_monthly * spec.static_ip_count
            line_items.append(CostLineItem(
                category="Network",
                description=f"Reserved external static IP x {spec.static_ip_count} ({spec.region})",
                sku_id="static-ip",
                unit="month",
                quantity=spec.static_ip_count,
                unit_price=ip_monthly,
                currency=currency,
                monthly_amount=round(ip_total, 2),
                source=provider.source_name,
            ))

        if spec.kubernetes_node_count is not None:
            k = requirement.kubernetes
            autopilot = k.autopilot if k else False
            mode_note = "Autopilot" if autopilot else "Standard"
            topology_note = "Regional" if k and k.regional else "Zonal"

            mgmt_hourly = provider.get_gke_cluster_management_hourly_price(autopilot=autopilot)
            mgmt_monthly = mgmt_hourly * HOURS_PER_MONTH
            line_items.append(CostLineItem(
                category="Compute",
                description=f"GKE cluster management fee ({mode_note}, {topology_note})",
                sku_id="gke-cluster-management",
                unit="hour",
                quantity=HOURS_PER_MONTH,
                unit_price=mgmt_hourly,
                currency=currency,
                monthly_amount=round(mgmt_monthly, 2),
                source=provider.source_name,
            ))

            # GKE Enterprise edition: a fleet-management surcharge billed
            # per requested vCPU/hour across the cluster, on top of the
            # management fee above - never eligible for Spot/CUD/SUD.
            if k and k.edition.value == "enterprise":
                total_vcpu = (
                    k.avg_pod_count * k.pod_vcpu if autopilot
                    else spec.kubernetes_node_count * k.node_vcpu * (3 if k.regional else 1)
                )
                if total_vcpu > 0:
                    ent_hourly = provider.get_gke_enterprise_edition_vcpu_hourly_price()
                    ent_monthly = ent_hourly * total_vcpu * HOURS_PER_MONTH
                    line_items.append(CostLineItem(
                        category="Compute",
                        description=f"GKE Enterprise edition fee, {total_vcpu:g} vCPU fleet-wide",
                        sku_id="gke-enterprise-edition",
                        unit="vCPU-hour",
                        quantity=round(total_vcpu * HOURS_PER_MONTH, 2),
                        unit_price=ent_hourly,
                        currency=currency,
                        monthly_amount=round(ent_monthly, 2),
                        source=provider.source_name,
                    ))

            if autopilot and k and k.avg_pod_count > 0:
                gke_hours = _gke_effective_hours(k.hours_per_day, k.days_per_month)
                spot_note = " (Spot Pods)" if is_gke_spot else ""

                vcpu_hourly = provider.get_gke_autopilot_pod_vcpu_hourly_price(spec.region, spot=is_gke_spot)
                vcpu_qty = gke_hours * k.avg_pod_count * k.pod_vcpu
                line_items.append(CostLineItem(
                    category="Compute",
                    description=f"GKE Autopilot pod vCPU{spot_note}: {k.avg_pod_count} pod(s) x {k.pod_vcpu:g} vCPU",
                    sku_id="gke-autopilot-vcpu",
                    unit="vCPU-hour",
                    quantity=round(vcpu_qty, 4),
                    unit_price=vcpu_hourly,
                    currency=currency,
                    monthly_amount=round(vcpu_qty * vcpu_hourly, 2),
                    source=provider.source_name,
                ))

                mem_hourly = provider.get_gke_autopilot_pod_memory_gib_hourly_price(spec.region, spot=is_gke_spot)
                mem_qty = gke_hours * k.avg_pod_count * k.pod_memory_gb
                line_items.append(CostLineItem(
                    category="Compute",
                    description=f"GKE Autopilot pod memory{spot_note}: {k.avg_pod_count} pod(s) x {k.pod_memory_gb:g} GB",
                    sku_id="gke-autopilot-memory",
                    unit="GiB-hour",
                    quantity=round(mem_qty, 4),
                    unit_price=mem_hourly,
                    currency=currency,
                    monthly_amount=round(mem_qty * mem_hourly, 2),
                    source=provider.source_name,
                ))

                if k.pod_ephemeral_storage_gb > 0:
                    storage_hourly = provider.get_gke_autopilot_pod_ephemeral_storage_gib_hourly_price(spec.region, spot=is_gke_spot)
                    storage_qty = gke_hours * k.avg_pod_count * k.pod_ephemeral_storage_gb
                    line_items.append(CostLineItem(
                        category="Storage",
                        description=f"GKE Autopilot pod ephemeral storage: {k.avg_pod_count} pod(s) x {k.pod_ephemeral_storage_gb:g} GB",
                        sku_id="gke-autopilot-ephemeral-storage",
                        unit="GiB-hour",
                        quantity=round(storage_qty, 4),
                        unit_price=storage_hourly,
                        currency=currency,
                        monthly_amount=round(storage_qty * storage_hourly, 2),
                        source=provider.source_name,
                    ))

            elif not autopilot and spec.kubernetes_node_count > 0 and k:
                gke_hours = _gke_effective_hours(k.hours_per_day, k.days_per_month)
                zone_multiplier = 3 if k.regional else 1
                total_nodes = spec.kubernetes_node_count * zone_multiplier
                family = k.machine_family.value
                spot_note = " (Spot)" if is_gke_spot else ""
                regional_note = f", {spec.kubernetes_node_count}/zone x 3 zones = {total_nodes} nodes" if k.regional else ""

                node_hourly = provider.get_compute_hourly_price_for_spec(k.node_vcpu, k.node_ram_gb, family, spec.region)
                node_qty = gke_hours * total_nodes
                line_items.append(CostLineItem(
                    category="Compute",
                    description=(
                        f"GKE Standard node pool{spot_note}: {total_nodes} x "
                        f"{family}-custom ({k.node_vcpu} vCPU, {k.node_ram_gb:g} GB){regional_note} ({spec.region})"
                    ),
                    sku_id="gke-node-pool-compute",
                    unit="hour",
                    quantity=round(node_qty, 2),
                    unit_price=node_hourly,
                    currency=currency,
                    monthly_amount=round(node_qty * node_hourly, 2),
                    source=provider.source_name,
                ))

                if k.node_disk_size_gb > 0:
                    disk_price = provider.get_disk_monthly_price_per_gb(k.node_disk_type.value, spec.region)
                    disk_monthly = disk_price * k.node_disk_size_gb * total_nodes
                    line_items.append(CostLineItem(
                        category="Storage",
                        description=f"GKE node boot disk: {k.node_disk_type.value} {k.node_disk_size_gb} GB x {total_nodes} node(s) ({spec.region})",
                        sku_id="gke-node-pool-disk",
                        unit="GB-month",
                        quantity=k.node_disk_size_gb * total_nodes,
                        unit_price=disk_price,
                        currency=currency,
                        monthly_amount=round(disk_monthly, 2),
                        source=provider.source_name,
                    ))

                if k.node_gpu_type != GpuType.NONE and k.node_gpu_count > 0:
                    gpu_hourly = provider.get_gpu_hourly_price(k.node_gpu_type.value, spec.region)
                    gpu_qty = gke_hours * k.node_gpu_count * total_nodes
                    line_items.append(CostLineItem(
                        category="GPU",
                        description=f"GKE node GPU{spot_note}: {k.node_gpu_type.value} x {k.node_gpu_count} per node, {total_nodes} node(s)",
                        sku_id="gke-node-pool-gpu",
                        unit="hour",
                        quantity=round(gpu_qty, 2),
                        unit_price=gpu_hourly,
                        currency=currency,
                        monthly_amount=round(gpu_qty * gpu_hourly, 2),
                        source=provider.source_name,
                    ))

        if extra_line_items:
            # Generic service-catalog line items (app/catalog/generic_pricing.py) -
            # already fully computed, just folded into totals/discounts/tax here
            # so that logic stays in exactly one place.
            line_items.extend(extra_line_items)

        subtotal = round(sum(li.monthly_amount for li in line_items), 2)

        # -- Discounts --------------------------------------------------------
        # Two independent discount buckets: Compute Engine's own compute/GPU
        # spend, and GKE Standard node pool compute/GPU spend - kept apart
        # because a GKE node pool has its own provisioning model (is_gke_spot)
        # that may disagree with the primary Compute Engine spec's. The GKE
        # cluster management fee and Enterprise edition surcharge are
        # deliberately excluded from both buckets (never Spot/CUD/SUD
        # eligible on real Google Cloud), and GKE Autopilot pod pricing
        # already bakes its own Spot Pods discount into the per-resource
        # rate returned by the provider, so it never enters a bucket either.
        # (`discounts` itself is declared at the top of this method, not
        # here, so the Cloud SQL block above can append its own commitment
        # discount before this section runs.)

        def _apply_bucket_discount(bucket_items: list[CostLineItem], bucket_is_spot: bool, family: str, label_suffix: str) -> None:
            bucket_amount = sum(li.monthly_amount for li in bucket_items)
            if bucket_amount <= 0:
                return
            if bucket_is_spot:
                # Spot/Preemptible capacity is never eligible for Sustained or
                # Committed Use Discounts on real Google Cloud (it's already a
                # steep discount off on-demand, and can be reclaimed at any
                # time), so this branch is mutually exclusive with both -
                # Spot wins even if a commitment_term_years was also supplied.
                spot_percent = provider.get_spot_discount_percent(family)
                if spot_percent > 0:
                    discounts.append(DiscountLineItem(
                        name=f"Spot/Preemptible VM Discount{label_suffix}",
                        description="Applied to compute and GPU line items for Spot-provisioned capacity. Spot instances are not eligible for Sustained or Committed Use Discounts.",
                        percent_off=spot_percent,
                        monthly_savings=round(bucket_amount * spot_percent / 100, 2),
                    ))
            elif commitment_term_years > 0:
                cud_percent = provider.get_committed_use_discount_percent(commitment_term_years)
                if cud_percent > 0:
                    discounts.append(DiscountLineItem(
                        name=f"{commitment_term_years}-Year Committed Use Discount{label_suffix}",
                        description="Applied to compute and GPU line items in exchange for a spend commitment.",
                        percent_off=cud_percent,
                        monthly_savings=round(bucket_amount * cud_percent / 100, 2),
                    ))
            else:
                sud_percent = provider.get_sustained_use_discount_percent()
                if sud_percent > 0:
                    discounts.append(DiscountLineItem(
                        name=f"Sustained Use Discount{label_suffix}",
                        description="Automatically applied for on-demand instances running a full billing month.",
                        percent_off=sud_percent,
                        monthly_savings=round(bucket_amount * sud_percent / 100, 2),
                    ))

        discountable_categories = {"Compute", "GPU"}
        vm_bucket = [
            li for li in line_items
            if li.category in discountable_categories and not li.sku_id.startswith("gke-")
        ]
        gke_bucket = [li for li in line_items if li.sku_id in _GKE_NODE_POOL_SKUS]

        _apply_bucket_discount(vm_bucket, is_spot, spec.family or "e2", "")
        _apply_bucket_discount(
            gke_bucket, is_gke_spot,
            requirement.kubernetes.machine_family.value if requirement.kubernetes else "e2",
            " (GKE node pool)",
        )

        discount_total = round(sum(d.monthly_savings for d in discounts), 2)
        after_discount = round(subtotal - discount_total, 2)

        tax_rate = settings.default_tax_rate_percent
        tax_monthly = round(after_discount * tax_rate / 100, 2)

        support_percent = settings.support_plan_percent
        support_monthly = round(after_discount * support_percent / 100, 2)

        total_monthly = round(after_discount + tax_monthly + support_monthly, 2)
        total_yearly = round(total_monthly * 12, 2)
        total_three_year = round(total_monthly * 36, 2)

        return CostBreakdown(
            currency=currency,
            line_items=line_items,
            discounts=discounts,
            subtotal_monthly=subtotal,
            discount_total_monthly=discount_total,
            tax_rate_percent=tax_rate,
            tax_monthly=tax_monthly,
            support_plan_percent=support_percent,
            support_monthly=support_monthly,
            total_monthly=total_monthly,
            total_yearly=total_yearly,
            total_three_year=total_three_year,
        )
