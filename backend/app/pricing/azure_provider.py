"""Mock implementation of PricingProvider for Azure, backed by
`azure_mock_data`. Deterministic and offline - same status/shape as
`MockGCPPricingProvider`/`AwsPricingProvider`. No live Azure Retail Prices
API integration is built this phase (see docs/ROADMAP.md Phase 9); a future
`AzureLivePricingProvider` could implement this exact interface without any
change to `PricingEngine` or anything above it."""
from app.core.constants import HOURS_PER_MONTH
from app.pricing import azure_mock_data
from app.pricing.base import PricingProvider


class AzurePricingProvider(PricingProvider):
    source_name = "azure_mock_catalog"

    def _region_multiplier(self, region: str) -> float:
        return azure_mock_data.REGION_MULTIPLIER.get(region, 1.0)

    def get_compute_hourly_price_for_spec(self, vcpu: int, ram_gb: float, family: str, region: str) -> float:
        rates = azure_mock_data.FAMILY_HOURLY_RATES.get(family)
        if rates is None:
            raise KeyError(f"No pricing data for machine family '{family}'")
        base = (vcpu * rates["vcpu"]) + (ram_gb * rates["ram_gb"])
        return round(base * self._region_multiplier(region), 6)

    def get_disk_monthly_price_per_gb(self, disk_type: str, region: str) -> float:
        base = azure_mock_data.DISK_PRICE_PER_GB_MONTH.get(disk_type)
        if base is None:
            raise KeyError(f"No pricing data for disk type '{disk_type}'")
        return round(base * self._region_multiplier(region), 6)

    def get_gpu_hourly_price(self, gpu_type: str, region: str) -> float:
        base = azure_mock_data.GPU_HOURLY_PRICE.get(gpu_type)
        if base is None:
            raise KeyError(f"No pricing data for GPU type '{gpu_type}'")
        return round(base * self._region_multiplier(region), 6)

    def get_cloud_sql_hourly_price(self, tier: str, region: str) -> float:
        base = azure_mock_data.CLOUD_SQL_HOURLY_PRICE.get(tier)
        if base is None:
            raise KeyError(f"No pricing data for Azure Database tier '{tier}'")
        return round(base * self._region_multiplier(region), 6)

    def get_cloud_sql_ha_multiplier(self) -> float:
        return azure_mock_data.CLOUD_SQL_HA_MULTIPLIER

    def get_cloud_sql_storage_monthly_price_per_gb(self, region: str) -> float:
        return round(azure_mock_data.CLOUD_SQL_STORAGE_PER_GB_MONTH * self._region_multiplier(region), 6)

    def get_cloud_sql_storage_type_multiplier(self, storage_type: str) -> float:
        return azure_mock_data.CLOUD_SQL_STORAGE_TYPE_MULTIPLIER.get(storage_type, 1.0)

    def get_cloud_sql_backup_storage_monthly_price_per_gb(self, region: str) -> float:
        return round(azure_mock_data.CLOUD_SQL_BACKUP_STORAGE_PER_GB_MONTH * self._region_multiplier(region), 6)

    def get_disk_provisioned_iops_monthly_price_per_iops(self, region: str) -> float:
        return round(azure_mock_data.DISK_PROVISIONED_IOPS_PER_IOPS_MONTH * self._region_multiplier(region), 6)

    def get_disk_provisioned_throughput_monthly_price_per_mbps(self, region: str) -> float:
        return round(azure_mock_data.DISK_PROVISIONED_THROUGHPUT_PER_MBPS_MONTH * self._region_multiplier(region), 6)

    def get_network_egress_price_per_gb(self, region: str) -> float:
        return round(azure_mock_data.NETWORK_EGRESS_PER_GB * self._region_multiplier(region), 6)

    def get_network_ingress_price_per_gb(self, region: str) -> float:
        return azure_mock_data.NETWORK_INGRESS_PER_GB

    def get_load_balancer_monthly_base_price(self, region: str) -> float:
        return round(azure_mock_data.LOAD_BALANCER_MONTHLY_BASE * self._region_multiplier(region), 6)

    def get_snapshot_monthly_price_per_gb(self, region: str) -> float:
        return round(azure_mock_data.SNAPSHOT_PRICE_PER_GB_MONTH * self._region_multiplier(region), 6)

    def get_gke_cluster_management_hourly_price(self, autopilot: bool) -> float:
        return (
            azure_mock_data.GKE_AUTOPILOT_CLUSTER_MANAGEMENT_HOURLY
            if autopilot
            else azure_mock_data.GKE_STANDARD_CLUSTER_MANAGEMENT_HOURLY
        )

    def get_gke_enterprise_edition_vcpu_hourly_price(self) -> float:
        return azure_mock_data.GKE_ENTERPRISE_EDITION_VCPU_HOURLY

    def get_gke_autopilot_pod_vcpu_hourly_price(self, region: str, spot: bool) -> float:
        base = azure_mock_data.GKE_AUTOPILOT_POD_VCPU_SPOT_HOURLY if spot else azure_mock_data.GKE_AUTOPILOT_POD_VCPU_HOURLY
        return round(base * self._region_multiplier(region), 6)

    def get_gke_autopilot_pod_memory_gib_hourly_price(self, region: str, spot: bool) -> float:
        base = azure_mock_data.GKE_AUTOPILOT_POD_MEMORY_GIB_SPOT_HOURLY if spot else azure_mock_data.GKE_AUTOPILOT_POD_MEMORY_GIB_HOURLY
        return round(base * self._region_multiplier(region), 6)

    def get_gke_autopilot_pod_ephemeral_storage_gib_hourly_price(self, region: str, spot: bool) -> float:
        base = (
            azure_mock_data.GKE_AUTOPILOT_POD_EPHEMERAL_STORAGE_GIB_SPOT_HOURLY if spot
            else azure_mock_data.GKE_AUTOPILOT_POD_EPHEMERAL_STORAGE_GIB_HOURLY
        )
        return round(base * self._region_multiplier(region), 6)

    def get_pubsub_price_per_gib(self, region: str) -> float:
        return round(azure_mock_data.PUBSUB_PRICE_PER_GIB * self._region_multiplier(region), 6)

    def get_pubsub_free_tier_gib_per_month(self) -> float:
        return azure_mock_data.PUBSUB_FREE_TIER_GIB_PER_MONTH

    def get_logging_price_per_gib(self, region: str) -> float:
        return round(azure_mock_data.LOGGING_PRICE_PER_GIB * self._region_multiplier(region), 6)

    def get_logging_free_tier_gib_per_month(self) -> float:
        return azure_mock_data.LOGGING_FREE_TIER_GIB_PER_MONTH

    def get_sustained_use_discount_percent(self) -> float:
        return azure_mock_data.SUSTAINED_USE_DISCOUNT_PERCENT

    def get_committed_use_discount_percent(self, term_years: int) -> float:
        return azure_mock_data.COMMITTED_USE_DISCOUNT_PERCENT.get(term_years, 0.0)

    def get_spot_discount_percent(self, family: str) -> float:
        return azure_mock_data.SPOT_DISCOUNT_PERCENT.get(family, 65.0)

    def get_os_license_hourly_price(self, operating_system: str, vcpu: int) -> float:
        per_vcpu = azure_mock_data.OS_LICENSE_HOURLY_PER_VCPU.get(operating_system)
        if per_vcpu is not None:
            return round(per_vcpu * vcpu, 6)
        return azure_mock_data.OS_LICENSE_HOURLY_FLAT.get(operating_system, 0.0)

    def get_local_ssd_monthly_price_per_disk(self, region: str) -> float:
        base = azure_mock_data.LOCAL_SSD_PRICE_PER_GB_MONTH * azure_mock_data.LOCAL_SSD_SIZE_GB
        return round(base * self._region_multiplier(region), 2)

    def get_static_ip_monthly_price(self, region: str) -> float:
        return round(azure_mock_data.STATIC_IP_HOURLY_PRICE * HOURS_PER_MONTH * self._region_multiplier(region), 2)

    def get_currency(self) -> str:
        return azure_mock_data.CURRENCY
