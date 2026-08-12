"""
PricingProvider interface.

CRITICAL INVARIANT: the AI/business-logic layers of this platform NEVER
compute a price themselves. Every dollar amount in a CostBreakdown originates
from a call into a PricingProvider implementation. Today that is
`MockGCPPricingProvider` (deterministic, offline, mirrors the shape of the
real Cloud Billing Catalog API). In production, `GcpPricingProvider` will
call https://cloudbilling.googleapis.com and implement this exact interface,
so `PricingEngine` and everything above it requires no changes.
"""
from abc import ABC, abstractmethod


class PricingProvider(ABC):
    source_name: str

    @abstractmethod
    def get_compute_hourly_price_for_spec(self, vcpu: int, ram_gb: float, family: str, region: str) -> float:
        """Priced by vCPU + RAM (Google Cloud's actual pricing model), not by
        machine type name alone, since custom machine types are priced this way."""
        ...

    @abstractmethod
    def get_disk_monthly_price_per_gb(self, disk_type: str, region: str) -> float: ...

    @abstractmethod
    def get_gpu_hourly_price(self, gpu_type: str, region: str) -> float: ...

    @abstractmethod
    def get_cloud_sql_hourly_price(self, tier: str, region: str) -> float: ...

    @abstractmethod
    def get_cloud_sql_storage_monthly_price_per_gb(self, region: str) -> float: ...

    @abstractmethod
    def get_cloud_sql_ha_multiplier(self) -> float: ...

    @abstractmethod
    def get_cloud_sql_storage_type_multiplier(self, storage_type: str) -> float:
        """HDD storage is cheaper than SSD (the Cloud SQL default) - a flat,
        publicly-advertised ratio rather than a separate per-region SKU,
        same modeling choice as get_cloud_sql_ha_multiplier above."""
        ...

    @abstractmethod
    def get_cloud_sql_backup_storage_monthly_price_per_gb(self, region: str) -> float:
        """Also used for binary log storage - Google bills both under the
        same backup-storage rate."""
        ...

    @abstractmethod
    def get_disk_provisioned_iops_monthly_price_per_iops(self, region: str) -> float:
        """Extreme PD / custom-provisioned-SSD only; 0 for other disk types."""
        ...

    @abstractmethod
    def get_disk_provisioned_throughput_monthly_price_per_mbps(self, region: str) -> float:
        """Extreme PD / custom-provisioned-SSD only; 0 for other disk types."""
        ...

    @abstractmethod
    def get_network_egress_price_per_gb(self, region: str) -> float: ...

    @abstractmethod
    def get_network_ingress_price_per_gb(self, region: str) -> float: ...

    @abstractmethod
    def get_load_balancer_monthly_base_price(self, region: str) -> float: ...

    @abstractmethod
    def get_snapshot_monthly_price_per_gb(self, region: str) -> float: ...

    @abstractmethod
    def get_gke_cluster_management_hourly_price(self, autopilot: bool) -> float: ...

    @abstractmethod
    def get_gke_enterprise_edition_vcpu_hourly_price(self) -> float:
        """Flat per-vCPU/hour surcharge for GKE Enterprise edition's fleet
        management features, on top of the regular cluster management fee
        and node/pod compute. Same flat, publicly-advertised-approximation
        modeling choice as get_spot_discount_percent/
        get_sustained_use_discount_percent below - Google does not publish
        this as a single reconcilable per-vCPU SKU."""
        ...

    @abstractmethod
    def get_gke_autopilot_pod_vcpu_hourly_price(self, region: str, spot: bool) -> float:
        """Autopilot bills by requested pod resources rather than by node -
        this is the general-purpose compute class vCPU-hour rate.
        `spot=True` returns the Spot Pods rate (Autopilot's own discount,
        already baked into the returned rate rather than layered on via the
        Spot/CUD/SUD discount line items PricingEngine applies to Compute
        Engine and GKE Standard nodes)."""
        ...

    @abstractmethod
    def get_gke_autopilot_pod_memory_gib_hourly_price(self, region: str, spot: bool) -> float: ...

    @abstractmethod
    def get_gke_autopilot_pod_ephemeral_storage_gib_hourly_price(self, region: str, spot: bool) -> float: ...

    @abstractmethod
    def get_pubsub_price_per_gib(self, region: str) -> float:
        """Pub/Sub Basic tier bills combined publish + delivery data volume
        (not message count) - $/GiB, applied on top of the free tier from
        `get_pubsub_free_tier_gib_per_month`."""
        ...

    @abstractmethod
    def get_pubsub_free_tier_gib_per_month(self) -> float:
        """A documented free allowance, not a Billing Catalog SKU price -
        both providers return the same published figure (10 GiB/month)."""
        ...

    @abstractmethod
    def get_logging_price_per_gib(self, region: str) -> float:
        """Cloud Logging ingestion - $/GiB, applied on top of the free tier
        from `get_logging_free_tier_gib_per_month`."""
        ...

    @abstractmethod
    def get_logging_free_tier_gib_per_month(self) -> float:
        """A documented free allowance, not a Billing Catalog SKU price -
        both providers return the same published figure (50 GiB/month)."""
        ...

    @abstractmethod
    def get_sustained_use_discount_percent(self) -> float: ...

    @abstractmethod
    def get_committed_use_discount_percent(self, term_years: int) -> float: ...

    @abstractmethod
    def get_spot_discount_percent(self, family: str) -> float:
        """Discount off the on-demand hourly price for a Spot/Preemptible VM
        of this machine family. Applied by PricingEngine as a discount line
        item, mutually exclusive with sustained/committed use discounts -
        the same modeling choice this codebase already uses for those (a
        flat, publicly-advertised percentage rather than a separately-priced
        SKU per family/region)."""
        ...

    @abstractmethod
    def get_os_license_hourly_price(self, operating_system: str, vcpu: int) -> float:
        """Per-instance hourly OS/license surcharge, on top of the
        infrastructure price - 0 for free Linux distributions. Google prices
        Windows Server per-vCPU and RHEL/SUSE as a flat per-instance rate;
        implementations decide which formula applies internally and return
        the already-resolved total hourly figure."""
        ...

    @abstractmethod
    def get_local_ssd_monthly_price_per_disk(self, region: str) -> float:
        """Monthly price for one fixed-size (375 GB) Local SSD block."""
        ...

    @abstractmethod
    def get_static_ip_monthly_price(self, region: str) -> float:
        """Monthly price for one reserved external static IP address."""
        ...

    @abstractmethod
    def get_currency(self) -> str: ...
