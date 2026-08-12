"""
Deterministic mock pricing data, structured the same way the real Google
Cloud Billing Catalog API prices SKUs (per-unit USD, per region). Values are
representative approximations of public GCP list pricing (as of early 2026)
for demo/offline purposes - NOT to be used for real customer invoicing.
Swap `MockGCPPricingProvider` for a live `GcpPricingProvider` for that.
"""

# USD per vCPU-hour and per GB-RAM-hour, by machine family (on-demand list price).
FAMILY_HOURLY_RATES = {
    "e2": {"vcpu": 0.021, "ram_gb": 0.00283},
    "n2": {"vcpu": 0.031, "ram_gb": 0.00417},
    "n2d": {"vcpu": 0.0271, "ram_gb": 0.00363},
    "c2": {"vcpu": 0.0348, "ram_gb": 0.00463},
    "a2": {"vcpu": 0.0315, "ram_gb": 0.00424},
}

# Regional price multiplier relative to us-central1 (baseline = 1.0).
REGION_MULTIPLIER = {
    "us-central1": 1.00,
    "us-east1": 1.00,
    "us-west1": 1.04,
    "europe-west1": 1.09,
    "europe-west4": 1.11,
    "asia-south1": 1.13,
    "asia-southeast1": 1.12,
}

DISK_PRICE_PER_GB_MONTH = {
    "pd-standard": 0.040,
    "pd-balanced": 0.100,
    "pd-ssd": 0.170,
    "pd-extreme": 0.125,  # + provisioned IOPS, simplified here
}

GPU_HOURLY_PRICE = {
    "nvidia-tesla-t4": 0.35,
    "nvidia-l4": 0.55,
    "nvidia-tesla-a100": 2.93,
    "nvidia-tesla-v100": 2.48,
}

CLOUD_SQL_HOURLY_PRICE = {
    "db-f1-micro": 0.0150,
    "db-g1-small": 0.0500,
    "db-custom-2-8192": 0.1218,
    "db-custom-4-16384": 0.2436,
    "db-custom-8-32768": 0.4872,
    "db-custom-16-65536": 0.9744,
    "db-custom-32-131072": 1.9488,
}
CLOUD_SQL_HA_MULTIPLIER = 2.0  # HA = synchronous standby in another zone, doubles compute cost
CLOUD_SQL_STORAGE_PER_GB_MONTH = 0.170  # SSD storage
CLOUD_SQL_STORAGE_TYPE_MULTIPLIER = {"ssd": 1.0, "hdd": 0.53}  # HDD is the cheaper, slower option
CLOUD_SQL_BACKUP_STORAGE_PER_GB_MONTH = 0.080  # also used for binary log storage

NETWORK_EGRESS_PER_GB = 0.12          # internet egress, tiered in reality; flat approximation
NETWORK_INGRESS_PER_GB = 0.0          # ingress to Google Cloud is free
LOAD_BALANCER_MONTHLY_BASE = 18.25    # ~5 forwarding rules worth of base cost, simplified flat fee
SNAPSHOT_PRICE_PER_GB_MONTH = 0.026

DISK_PROVISIONED_IOPS_PER_IOPS_MONTH = 0.065          # Extreme PD / custom-provisioned SSD only
DISK_PROVISIONED_THROUGHPUT_PER_MBPS_MONTH = 0.048    # Extreme PD / custom-provisioned SSD only

GKE_STANDARD_CLUSTER_MANAGEMENT_HOURLY = 0.10  # per cluster, beyond the free tier
GKE_AUTOPILOT_CLUSTER_MANAGEMENT_HOURLY = 0.10

# GKE Enterprise edition: a flat per-vCPU/hour fleet-management surcharge
# approximation (Google does not publish this as a single reconcilable SKU -
# same status as SUSTAINED_USE_DISCOUNT_PERCENT/SPOT_DISCOUNT_PERCENT below).
GKE_ENTERPRISE_EDITION_VCPU_HOURLY = 0.0083

# GKE Autopilot: bills by requested pod resources (general-purpose compute
# class, on-demand list price) rather than by node. Spot Pods rates are
# Autopilot's own steep discount off these on-demand figures.
GKE_AUTOPILOT_POD_VCPU_HOURLY = 0.0445
GKE_AUTOPILOT_POD_VCPU_SPOT_HOURLY = 0.0089
GKE_AUTOPILOT_POD_MEMORY_GIB_HOURLY = 0.0049
GKE_AUTOPILOT_POD_MEMORY_GIB_SPOT_HOURLY = 0.0011
GKE_AUTOPILOT_POD_EPHEMERAL_STORAGE_GIB_HOURLY = 0.0001
GKE_AUTOPILOT_POD_EPHEMERAL_STORAGE_GIB_SPOT_HOURLY = 0.00003

# Pub/Sub Basic tier: $40 per TiB of combined publish + delivery data volume
# (Google's actual billing unit is data volume, not message count).
# 1 TiB = 1024 GiB -> 40 / 1024 = $0.0390625 per GiB.
PUBSUB_PRICE_PER_GIB = 40.0 / 1024
# Google's documented free allowance: first 10 GiB/month of combined
# publish+delivery traffic, per project - a billing policy constant, not a
# priced SKU, so both the mock and live provider return this same figure.
PUBSUB_FREE_TIER_GIB_PER_MONTH = 10.0

# Cloud Logging: $0.50/GiB ingested beyond the free allowance.
LOGGING_PRICE_PER_GIB = 0.50
# Google's documented free allowance: first 50 GiB/month of log ingestion,
# per project - a billing policy constant, not a priced SKU.
LOGGING_FREE_TIER_GIB_PER_MONTH = 50.0

SUSTAINED_USE_DISCOUNT_PERCENT = 20.0   # ~20% for instances running a full month, N1/E2/N2 family approximation

COMMITTED_USE_DISCOUNT_PERCENT = {
    1: 25.0,   # 1-year commitment
    3: 45.0,   # 3-year commitment
}

# Spot (formerly "Preemptible") VM discount off on-demand, by family. Real
# Google Cloud Spot pricing varies by family/region/moment (it is a dynamic
# market price, capped at ~60-91% off list) - this is a representative flat
# per-family approximation, same status as every other mock pricing figure
# in this module.
SPOT_DISCOUNT_PERCENT = {
    "e2": 60.0,
    "n2": 60.0,
    "n2d": 60.0,
    "c2": 55.0,
    "a2": 50.0,
}

# OS/license hourly surcharge, added on top of the Compute Engine
# infrastructure price. Windows Server is priced per-vCPU on real Google
# Cloud; RHEL/SUSE are priced as a flat per-instance rate up to a small-
# instance tier (a real invoice may step up above ~4 vCPU - not modeled
# here, same approximation-not-invoicing-grade status as the rest of this
# file). "linux" (free distributions) intentionally has no entry in either
# table below, so it resolves to $0.00.
OS_LICENSE_HOURLY_PER_VCPU = {
    "windows_server": 0.04,
}
OS_LICENSE_HOURLY_FLAT = {
    "rhel": 0.06,
    "suse": 0.02,
}

LOCAL_SSD_SIZE_GB = 375  # fixed block size Google sells Local SSD in
LOCAL_SSD_PRICE_PER_GB_MONTH = 0.080

STATIC_IP_HOURLY_PRICE = 0.010  # reserved-but-unattached external IP address

CURRENCY = "USD"
