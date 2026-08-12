"""
Deterministic mock AWS pricing data, structured the same way
`app/pricing/mock_data.py` structures GCP pricing - per-unit USD, by
canonical family/region code (see `app/catalog/aws_provider.py` for the
canonical-vocabulary explanation). Values are representative approximations
of public AWS on-demand list pricing (us-east-2 baseline, early 2026) for
demo/comparison purposes - NOT to be used for real customer invoicing.
"""

# USD per vCPU-hour and per GB-RAM-hour, by canonical family code.
FAMILY_HOURLY_RATES = {
    "e2": {"vcpu": 0.0250, "ram_gb": 0.00350},   # T3 (burstable)
    "n2": {"vcpu": 0.0340, "ram_gb": 0.00470},   # M5 (general purpose)
    "n2d": {"vcpu": 0.0292, "ram_gb": 0.00400},  # M6a (AMD general purpose)
    "c2": {"vcpu": 0.0425, "ram_gb": 0.00570},   # C5 (compute optimized)
    "a2": {"vcpu": 0.0320, "ram_gb": 0.00430},   # G4dn/P3/P4d base compute (GPU priced separately)
}

# Regional price multiplier relative to us-east-2 (canonical us-central1, baseline = 1.0).
REGION_MULTIPLIER = {
    "us-central1": 1.00,       # us-east-2
    "us-east1": 1.00,          # us-east-1
    "us-west1": 1.03,          # us-west-2
    "europe-west1": 1.08,      # eu-west-1
    "europe-west4": 1.10,      # eu-central-1
    "asia-south1": 1.14,       # ap-south-1
    "asia-southeast1": 1.16,   # ap-southeast-1
}

DISK_PRICE_PER_GB_MONTH = {
    "pd-standard": 0.045,   # EBS st1
    "pd-balanced": 0.080,   # EBS gp3
    "pd-ssd": 0.125,        # EBS io1 (+ provisioned IOPS, simplified here)
    "pd-extreme": 0.125,    # EBS io2 Block Express (+ provisioned IOPS, simplified here)
}

GPU_HOURLY_PRICE = {
    "nvidia-tesla-t4": 0.526,      # g4dn.xlarge GPU share
    "nvidia-l4": 0.60,             # approximate, AWS G6 family
    "nvidia-tesla-a100": 4.10,     # p4d.24xlarge GPU share
    "nvidia-tesla-v100": 3.06,     # p3.8xlarge GPU share
}

CLOUD_SQL_HOURLY_PRICE = {
    "db.t3.micro": 0.0180,
    "db.m5.large": 0.1710,
    "db.m5.xlarge": 0.3420,
    "db.m5.2xlarge": 0.6840,
    "db.m5.4xlarge": 1.3680,
    "db.m5.8xlarge": 2.7360,
}
CLOUD_SQL_HA_MULTIPLIER = 2.0  # Multi-AZ deployment, doubles compute cost
CLOUD_SQL_STORAGE_PER_GB_MONTH = 0.115  # RDS gp3 storage
CLOUD_SQL_STORAGE_TYPE_MULTIPLIER = {"ssd": 1.0, "hdd": 0.56}  # gp3 SSD vs magnetic
CLOUD_SQL_BACKUP_STORAGE_PER_GB_MONTH = 0.095  # RDS backup storage

NETWORK_EGRESS_PER_GB = 0.09          # internet egress, tiered in reality; flat approximation
NETWORK_INGRESS_PER_GB = 0.0          # ingress to AWS is free
LOAD_BALANCER_MONTHLY_BASE = 16.20    # Application Load Balancer base hourly cost x 730, simplified flat fee
SNAPSHOT_PRICE_PER_GB_MONTH = 0.05    # EBS snapshot (S3-backed)

DISK_PROVISIONED_IOPS_PER_IOPS_MONTH = 0.065          # io2 provisioned IOPS
DISK_PROVISIONED_THROUGHPUT_PER_MBPS_MONTH = 0.040    # gp3 provisioned throughput

GKE_STANDARD_CLUSTER_MANAGEMENT_HOURLY = 0.10  # EKS control plane, per cluster
GKE_AUTOPILOT_CLUSTER_MANAGEMENT_HOURLY = 0.10  # EKS control plane (Fargate nodes billed separately, not modeled)

GKE_ENTERPRISE_EDITION_VCPU_HOURLY = 0.0083  # EKS equivalent fleet-management surcharge approximation, per vCPU-hour

# EKS Fargate (the AWS analogue to GKE Autopilot's per-pod billing): vCPU +
# memory billed per second at Fargate on-demand list price; Fargate Spot is
# the discounted equivalent of Autopilot Spot Pods. AWS Fargate does not
# bill ephemeral storage as a separate per-GB-hour SKU below its included
# 20 GiB, so that figure is a small representative approximation.
GKE_AUTOPILOT_POD_VCPU_HOURLY = 0.04048
GKE_AUTOPILOT_POD_VCPU_SPOT_HOURLY = 0.01214
GKE_AUTOPILOT_POD_MEMORY_GIB_HOURLY = 0.004445
GKE_AUTOPILOT_POD_MEMORY_GIB_SPOT_HOURLY = 0.001334
GKE_AUTOPILOT_POD_EPHEMERAL_STORAGE_GIB_HOURLY = 0.0001
GKE_AUTOPILOT_POD_EPHEMERAL_STORAGE_GIB_SPOT_HOURLY = 0.00003

# SNS+SQS have no single unified $/GiB list price (both are billed per
# request/notification, not per data volume) - this is a rough data-volume
# equivalent for cross-cloud comparison purposes only, not a real AWS SKU.
PUBSUB_PRICE_PER_GIB = 0.045
PUBSUB_FREE_TIER_GIB_PER_MONTH = 1.0    # SNS/SQS free tiers are request-based; approximated here
LOGGING_PRICE_PER_GIB = 0.50            # CloudWatch Logs ingestion
LOGGING_FREE_TIER_GIB_PER_MONTH = 5.0   # CloudWatch Logs free tier (first 5 GB/month)

# AWS has no automatic usage-based discount analogous to GCP's Sustained Use
# Discount - on-demand stays on-demand unless a commitment (Savings Plan /
# Reserved Instance) is purchased. This is a genuine, meaningful cross-cloud
# difference, not an oversight - see docs/ROADMAP.md Phase 9.
SUSTAINED_USE_DISCOUNT_PERCENT = 0.0

# Approximate no-upfront Compute Savings Plan discount rates.
COMMITTED_USE_DISCOUNT_PERCENT = {
    1: 28.0,   # 1-year commitment
    3: 52.0,   # 3-year commitment
}

# AWS Spot Instance discount off on-demand, by canonical family code - a
# dynamic market price on real AWS (typically ~60-90% off), approximated
# flat here like every other figure in this module.
SPOT_DISCOUNT_PERCENT = {
    "e2": 65.0,
    "n2": 65.0,
    "n2d": 65.0,
    "c2": 60.0,
    "a2": 55.0,
}

# OS/license hourly surcharge on top of the EC2 infrastructure price -
# same simplified per-vCPU (Windows) / flat-per-instance (RHEL/SUSE) model
# `app/pricing/mock_data.py` uses, approximated to AWS's public Windows/
# RHEL/SUSE AMI surcharge pricing. "linux" has no entry -> $0.00.
OS_LICENSE_HOURLY_PER_VCPU = {
    "windows_server": 0.046,
}
OS_LICENSE_HOURLY_FLAT = {
    "rhel": 0.06,
    "suse": 0.02,
}

LOCAL_SSD_SIZE_GB = 375  # NVMe instance-store equivalent block, for cross-cloud comparability
LOCAL_SSD_PRICE_PER_GB_MONTH = 0.10  # instance-store capacity is bundled into instance price on real AWS; approximated here as a standalone add-on for comparability

STATIC_IP_HOURLY_PRICE = 0.005  # idle/unattached Elastic IP address

CURRENCY = "USD"
