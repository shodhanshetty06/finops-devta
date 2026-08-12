"""
Deterministic mock Azure pricing data, structured the same way
`app/pricing/mock_data.py` structures GCP pricing - per-unit USD, by
canonical family/region code (see `app/catalog/azure_provider.py` for the
canonical-vocabulary explanation). Values are representative approximations
of public Azure pay-as-you-go pricing (Central US baseline, early 2026) for
demo/comparison purposes - NOT to be used for real customer invoicing.
"""

# USD per vCPU-hour and per GB-RAM-hour, by canonical family code.
FAMILY_HOURLY_RATES = {
    "e2": {"vcpu": 0.0240, "ram_gb": 0.00330},   # Bsv2 (burstable)
    "n2": {"vcpu": 0.0330, "ram_gb": 0.00460},   # Dsv5 (general purpose)
    "n2d": {"vcpu": 0.0285, "ram_gb": 0.00390},  # Dasv5 (AMD general purpose)
    "c2": {"vcpu": 0.0415, "ram_gb": 0.00560},   # Fsv2 (compute optimized)
    "a2": {"vcpu": 0.0310, "ram_gb": 0.00420},   # NC-series base compute (GPU priced separately)
}

# Regional price multiplier relative to Central US (canonical us-central1, baseline = 1.0).
REGION_MULTIPLIER = {
    "us-central1": 1.00,       # Central US
    "us-east1": 1.00,          # East US
    "us-west1": 1.03,          # West US 2
    "europe-west1": 1.09,      # West Europe
    "europe-west4": 1.11,      # Germany West Central
    "asia-south1": 1.15,       # Central India
    "asia-southeast1": 1.17,   # Southeast Asia
}

DISK_PRICE_PER_GB_MONTH = {
    "pd-standard": 0.048,   # Standard HDD
    "pd-balanced": 0.096,   # Standard SSD
    "pd-ssd": 0.135,        # Premium SSD
    "pd-extreme": 0.135,    # Ultra Disk (+ provisioned IOPS/throughput, simplified here)
}

GPU_HOURLY_PRICE = {
    "nvidia-tesla-t4": 0.55,       # NC4as_T4_v3 GPU share
    "nvidia-l4": 0.65,             # approximate, Azure NVadsA10 family used as proxy
    "nvidia-tesla-a100": 3.67,     # ND96asr_v4 GPU share
    "nvidia-tesla-v100": 3.06,     # NC24s_v3 GPU share
}

CLOUD_SQL_HOURLY_PRICE = {
    "Standard_B1ms (DB)": 0.0200,
    "GP_Gen5_2": 0.1860,
    "GP_Gen5_4": 0.3720,
    "GP_Gen5_8": 0.7440,
    "GP_Gen5_16": 1.4880,
    "GP_Gen5_32": 2.9760,
}
CLOUD_SQL_HA_MULTIPLIER = 2.0  # Zone-redundant HA, doubles compute cost
CLOUD_SQL_STORAGE_PER_GB_MONTH = 0.12  # Azure Database Premium SSD storage
CLOUD_SQL_STORAGE_TYPE_MULTIPLIER = {"ssd": 1.0, "hdd": 0.5}  # Premium SSD vs Standard HDD
CLOUD_SQL_BACKUP_STORAGE_PER_GB_MONTH = 0.10  # Azure Database backup storage

NETWORK_EGRESS_PER_GB = 0.087         # internet egress, tiered in reality; flat approximation
NETWORK_INGRESS_PER_GB = 0.0          # ingress to Azure is free
LOAD_BALANCER_MONTHLY_BASE = 18.25    # Standard Load Balancer base hourly cost x 730, simplified flat fee
SNAPSHOT_PRICE_PER_GB_MONTH = 0.05    # Managed disk snapshot

DISK_PROVISIONED_IOPS_PER_IOPS_MONTH = 0.065          # Ultra Disk provisioned IOPS
DISK_PROVISIONED_THROUGHPUT_PER_MBPS_MONTH = 0.045    # Ultra Disk provisioned throughput

GKE_STANDARD_CLUSTER_MANAGEMENT_HOURLY = 0.10  # AKS Standard tier control plane, per cluster
GKE_AUTOPILOT_CLUSTER_MANAGEMENT_HOURLY = 0.10  # AKS Standard tier control plane (virtual nodes billed separately, not modeled)

GKE_ENTERPRISE_EDITION_VCPU_HOURLY = 0.0083  # AKS Uptime SLA/fleet-management equivalent surcharge approximation, per vCPU-hour

# AKS Virtual Nodes / ACI (the Azure analogue to GKE Autopilot's per-pod
# billing): vCPU + memory billed per second at ACI on-demand list price;
# ACI Spot is the discounted equivalent of Autopilot Spot Pods.
GKE_AUTOPILOT_POD_VCPU_HOURLY = 0.0468
GKE_AUTOPILOT_POD_VCPU_SPOT_HOURLY = 0.0140
GKE_AUTOPILOT_POD_MEMORY_GIB_HOURLY = 0.00514
GKE_AUTOPILOT_POD_MEMORY_GIB_SPOT_HOURLY = 0.00154
GKE_AUTOPILOT_POD_EPHEMERAL_STORAGE_GIB_HOURLY = 0.0001
GKE_AUTOPILOT_POD_EPHEMERAL_STORAGE_GIB_SPOT_HOURLY = 0.00003

# Azure Service Bus/Event Grid have no single unified $/GiB list price (both
# are billed per operation, not per data volume) - this is a rough
# data-volume equivalent for cross-cloud comparison purposes only, not a
# real Azure meter.
PUBSUB_PRICE_PER_GIB = 0.05
PUBSUB_FREE_TIER_GIB_PER_MONTH = 1.0     # Service Bus/Event Grid free tiers are operation-based; approximated here
LOGGING_PRICE_PER_GIB = 2.30              # Azure Monitor Log Analytics ingestion (pay-as-you-go tier)
LOGGING_FREE_TIER_GIB_PER_MONTH = 5.0    # Log Analytics free tier (first 5 GB/month per workspace)

# Azure has no automatic usage-based discount analogous to GCP's Sustained
# Use Discount - pay-as-you-go stays pay-as-you-go unless a Reservation is
# purchased. See docs/ROADMAP.md Phase 9.
SUSTAINED_USE_DISCOUNT_PERCENT = 0.0

# Approximate Azure Reserved VM Instance discount rates (pay-as-you-go term).
COMMITTED_USE_DISCOUNT_PERCENT = {
    1: 30.0,   # 1-year reservation
    3: 55.0,   # 3-year reservation
}

# Azure Spot VM discount off pay-as-you-go, by canonical family code - a
# dynamic market price on real Azure (typically ~60-90% off), approximated
# flat here like every other figure in this module.
SPOT_DISCOUNT_PERCENT = {
    "e2": 65.0,
    "n2": 65.0,
    "n2d": 65.0,
    "c2": 60.0,
    "a2": 55.0,
}

# OS/license hourly surcharge on top of the VM infrastructure price - same
# simplified per-vCPU (Windows) / flat-per-instance (RHEL/SUSE) model
# `app/pricing/mock_data.py` uses (Azure Hybrid Benefit, which lets
# customers reuse existing licenses, is not modeled here). "linux" has no
# entry -> $0.00.
OS_LICENSE_HOURLY_PER_VCPU = {
    "windows_server": 0.04,
}
OS_LICENSE_HOURLY_FLAT = {
    "rhel": 0.06,
    "suse": 0.02,
}

LOCAL_SSD_SIZE_GB = 375  # temp-disk equivalent block, for cross-cloud comparability
LOCAL_SSD_PRICE_PER_GB_MONTH = 0.095  # Azure temp disk capacity is bundled into VM price on real Azure; approximated here as a standalone add-on for comparability

STATIC_IP_HOURLY_PRICE = 0.0045  # unattached Standard SKU public IP address

CURRENCY = "USD"
