"""Static GCP service catalog data. This is the single place that lists
every service the "New Estimate" service catalog can offer - adding a new
service means adding one `GCPServiceDefinition` entry here, never touching
frontend components or the pipeline (`services/estimation_service.py`,
`validation/rules.py`, `catalog/generic_pricing.py` all consume this list
generically, keyed only by `service_id`/`category`/`configuration_schema`/
`pricing_dimensions`).

A handful of services declare `legacy_binding` - their configuration_schema
field ids are chosen to exactly match the corresponding legacy typed model
(StorageRequirement/DatabaseRequirement/KubernetesRequirement) so
`catalog/service_catalog_bridge.py` can build that model with a plain
`model_validate(config)` and hand off to the existing,
exact PricingProvider-backed pricing/validation/normalization instead of the
generic calculator below. Every other service has no existing typed model or
pricing method, so it is priced by `GenericServicePricingCalculator`: each
`pricing_dimensions` entry is `monthly_amount = (config[config_field_id] /
quantity_divisor) * unit_price_usd`, using indicative public list pricing
(never a live GCP Billing Catalog lookup) - always surfaced as an
`Assumption`, never silently presented as exact.

Every numeric field defaults to 0 (or to its `min_value` when that is above
0 - e.g. Spanner's 100-processing-unit minimum) so a freshly added service
starts at "no usage" instead of a prefilled guess.
"""
from app.catalog.service_catalog import (
    ConfigFieldOption,
    ConfigFieldSchema,
    GCPServiceDefinition,
    PricingDimension,
)

CAT_COMPUTE = "Compute"
CAT_STORAGE = "Storage"
CAT_DATABASE = "Database"
CAT_NETWORKING = "Networking"
CAT_MESSAGING = "Messaging & Eventing"
CAT_ANALYTICS = "Analytics & Data"
CAT_AI_ML = "AI/ML"
CAT_SECURITY = "Security"
CAT_OBSERVABILITY = "Observability"
CAT_DEVOPS = "DevOps"
CAT_INTEGRATION = "API & Integration"

SERVICE_CATEGORIES = [
    CAT_COMPUTE, CAT_STORAGE, CAT_DATABASE, CAT_NETWORKING, CAT_MESSAGING,
    CAT_ANALYTICS, CAT_AI_ML, CAT_SECURITY, CAT_OBSERVABILITY, CAT_DEVOPS,
    CAT_INTEGRATION,
]


def _f(field_id: str, label: str, field_type: str = "number", **kwargs) -> ConfigFieldSchema:
    return ConfigFieldSchema(field_id=field_id, label=label, field_type=field_type, **kwargs)


def _opts(*pairs: tuple[str, str]) -> list[ConfigFieldOption]:
    return [ConfigFieldOption(value=v, label=lbl) for v, lbl in pairs]


def _d(dimension_id: str, label: str, config_field_id: str, unit_label: str,
       unit_price_usd: float, quantity_divisor: float = 1.0,
       rate_selector_field_id: str | None = None,
       rate_by_option: dict[str, float] | None = None) -> PricingDimension:
    return PricingDimension(
        dimension_id=dimension_id, label=label, config_field_id=config_field_id,
        unit_label=unit_label, unit_price_usd=unit_price_usd, quantity_divisor=quantity_divisor,
        rate_selector_field_id=rate_selector_field_id, rate_by_option=rate_by_option,
    )


# Shared by every service priced with region-sensitive dimensions (see
# catalog/generic_pricing.py's _region_multiplier) - same 7-region list the
# rest of the app already uses (app.domain.enums.Region), kept as a plain
# tuple here to avoid a domain-layer import into the catalog data module.
_REGION_OPTIONS = _opts(
    ("us-central1", "us-central1 (Iowa)"),
    ("us-east1", "us-east1 (South Carolina)"),
    ("us-west1", "us-west1 (Oregon)"),
    ("europe-west1", "europe-west1 (Belgium)"),
    ("europe-west4", "europe-west4 (Netherlands)"),
    ("asia-south1", "asia-south1 (Mumbai)"),
    ("asia-southeast1", "asia-southeast1 (Singapore)"),
)


def _region_field(group: str = "Region / Location") -> ConfigFieldSchema:
    return _f("region", "Region", "select", default="us-central1", required=False,
               options=_REGION_OPTIONS, group=group,
               help_text="Applies a regional price multiplier to this service's cost, same as the rest of the estimate.")


GCP_SERVICE_CATALOG: list[GCPServiceDefinition] = [
    # -- Compute --------------------------------------------------------
    GCPServiceDefinition(
        service_id="compute-engine",
        display_name="Compute Engine",
        category=CAT_COMPUTE,
        description="Virtual machines. Sized via the Sizing section above - selecting this card just marks it as part of your architecture.",
        icon="cpu",
        configuration_schema=[],
        pricing_dimensions=[],
    ),
    GCPServiceDefinition(
        service_id="gke",
        display_name="GKE",
        category=CAT_COMPUTE,
        description=(
            "Google Kubernetes Engine - Autopilot (pay per pod resource request) or Standard "
            "(pay per node) cluster. Persistent volume claims price via the Persistent Disk "
            "card; load balancers, Cloud CDN, VPN, egress, and Cloud NAT price via their own "
            "Networking cards - add those alongside this one instead of re-entering them here."
        ),
        icon="container",
        legacy_binding="kubernetes",
        configuration_schema=[
            _f("autopilot", "Autopilot mode", "boolean", default=False, required=False,
               help_text="On = Autopilot. Off = Standard. Switches which fields below are priced."),
            _f("edition", "Edition", "select", default="standard", required=False,
               options=_opts(("standard", "Standard"), ("enterprise", "Enterprise")),
               help_text="Enterprise adds a fleet-management surcharge per vCPU/hour."),
            _f("regional", "Regional cluster", "boolean", default=False, required=False,
               help_text="Regional (3-zone, high-availability) vs. Zonal. Standard mode replicates the node pool across all 3 zones."),
            _f("provisioning_model", "Provisioning model", "select", default="on_demand", required=False,
               options=_opts(("on_demand", "On-demand"), ("spot", "Spot")),
               help_text="Spot Standard nodes / Spot Pods. Not eligible for Sustained or Committed Use Discounts."),

            _f("node_count", "Node count", unit="nodes/zone", default=0, min_value=0, required=False,
               help_text="Standard mode only. Nodes per zone - a Regional cluster runs this many in each of 3 zones."),
            _f("machine_family", "Node machine family", "select", default="e2", required=False,
               options=_opts(("e2", "E2"), ("n2", "N2"), ("n2d", "N2D"), ("c2", "C2"), ("a2", "A2 (GPU-optimized)"))),
            _f("node_vcpu", "vCPU per node", unit="vCPU", default=4, min_value=1, required=False),
            _f("node_ram_gb", "RAM per node", unit="GB", default=16, min_value=0.5, required=False),
            _f("node_disk_type", "Node boot disk type", "select", default="pd-balanced", required=False,
               options=_opts(("pd-standard", "Standard"), ("pd-balanced", "Balanced"), ("pd-ssd", "SSD"), ("pd-extreme", "Extreme"))),
            _f("node_disk_size_gb", "Node boot disk size", unit="GB", default=100, min_value=10, required=False),
            _f("node_gpu_type", "Node GPU type", "select", default="none", required=False,
               options=_opts(("none", "None"), ("nvidia-tesla-t4", "NVIDIA T4"), ("nvidia-l4", "NVIDIA L4"),
                              ("nvidia-tesla-a100", "NVIDIA A100 40GB"), ("nvidia-tesla-v100", "NVIDIA V100"))),
            _f("node_gpu_count", "GPUs per node", unit="GPUs", default=0, min_value=0, required=False),

            _f("avg_pod_count", "Average concurrent pods", unit="pods", default=0, min_value=0, required=False,
               help_text="Autopilot mode only."),
            _f("pod_vcpu", "vCPU per pod", unit="vCPU", default=0.25, min_value=0.25, required=False),
            _f("pod_memory_gb", "Memory per pod", unit="GB", default=0.5, min_value=0.5, required=False),
            _f("pod_ephemeral_storage_gb", "Ephemeral storage per pod", unit="GB", default=1, min_value=0, required=False),

            _f("hours_per_day", "Hours/day", unit="hours", default=None, min_value=0.1, max_value=24, required=False,
               help_text="Leave blank to run 24/7."),
            _f("days_per_month", "Days/month", unit="days", default=None, min_value=1, max_value=31, required=False,
               help_text="Leave blank for every day."),
        ],
    ),
    GCPServiceDefinition(
        service_id="cloud-run",
        display_name="Cloud Run",
        category=CAT_COMPUTE,
        description="Fully managed serverless containers.",
        icon="zap",
        configuration_schema=[
            _region_field(),

            _f("cpu_allocation", "CPU allocation", "select", default="request_only", required=False,
               options=_opts(("request_only", "Only during request processing"), ("always_allocated", "CPU is always allocated")),
               group="Pricing Allocation",
               help_text="Always-allocated bills idle minimum instances for the full month; request-only throttles CPU between requests."),

            _f("vcpu_count", "vCPU", unit="vCPU", default=1, min_value=0.08, group="CPU & Memory Allocation"),
            _f("memory_gb", "Memory", unit="GB", default=0.5, min_value=0.128, group="CPU & Memory Allocation"),

            _f("concurrency", "Concurrency", unit="requests/instance", default=80, min_value=1, max_value=1000, group="Concurrency Level"),

            _f("requests_per_month", "Total requests", unit="requests/month", default=0, group="Execution Metrics"),
            _f("avg_duration_ms", "Average request duration", unit="ms", default=0, group="Execution Metrics"),

            _f("min_instances", "Minimum instances", unit="idle instances", default=0, min_value=0, required=False, group="Scaling Constraints"),
            _f("max_instances", "Maximum instances", default=100, min_value=0, required=False, group="Scaling Constraints"),

            _f("egress_gb_per_month", "Outbound egress", unit="GB/month", default=0, required=False, group="Ingress & Networking"),
            _f("vpc_connector_size", "VPC Access Connector size", "select", default="none", required=False,
               options=_opts(("none", "None"), ("small", "Small (200-300 Mbps, 2-3 instances)"), ("large", "Large (300-1000 Mbps, up to 10 instances)")),
               group="Ingress & Networking",
               help_text="Only needed if this service reaches an internal VPC network."),
        ],
        pricing_dimensions=[
            _d("requests", "Requests", "requests_per_month", "million requests", 0.40, 1_000_000),
            _d("vcpu-time", "vCPU time", "vcpu_seconds_per_month", "1,000 vCPU-sec", 0.024, 1_000),
            _d("memory-time", "Memory time", "gb_seconds_per_month", "1,000 GB-sec", 0.0025, 1_000),
            _d("egress", "Egress", "egress_gb_per_month", "GB", 0.12),
            _d("vpc-connector", "VPC Access Connector", "vpc_connector_flag", "month", 0.0,
               rate_selector_field_id="vpc_connector_size", rate_by_option={"none": 0.0, "small": 50.0, "large": 150.0}),
        ],
    ),
    GCPServiceDefinition(
        service_id="cloud-run-functions",
        display_name="Cloud Run functions",
        category=CAT_COMPUTE,
        description="Event-driven functions (formerly Cloud Functions).",
        icon="zap",
        configuration_schema=[
            _region_field(),

            _f("memory_mb", "Memory size", "select", default="256", required=False,
               group="Architecture / Memory Provisioning",
               options=_opts(("128", "128 MB (0.083 vCPU)"), ("256", "256 MB (0.167 vCPU)"), ("512", "512 MB (0.333 vCPU)"),
                              ("1024", "1 GB (0.583 vCPU)"), ("2048", "2 GB (1 vCPU)"), ("4096", "4 GB (2 vCPU)"),
                              ("8192", "8 GB (2 vCPU)"), ("16384", "16 GB (4 vCPU)"), ("32768", "32 GB (8 vCPU)")),
               help_text="Allocated vCPU is fixed by the memory tier, matching Google's gen2 Cloud Functions pairing."),

            _f("invocations_per_month", "Invocations", unit="invocations/month", default=0, group="Invocations"),

            _f("avg_execution_time_ms", "Average execution time", unit="ms/call", default=0, group="Execution Time"),

            _f("egress_gb_per_month", "Network egress", unit="GB/month", default=0, required=False, group="Network Egress"),
        ],
        pricing_dimensions=[
            _d("invocations", "Invocations", "invocations_per_month", "million invocations", 0.40, 1_000_000),
            _d("vcpu-time", "vCPU time", "vcpu_seconds_per_month", "1,000 vCPU-sec", 0.024, 1_000),
            _d("memory-time", "Memory time", "gb_seconds_per_month", "1,000 GB-sec", 0.0025, 1_000),
            _d("egress", "Egress", "egress_gb_per_month", "GB", 0.12),
        ],
    ),

    # -- Storage ----------------------------------------------------------
    GCPServiceDefinition(
        service_id="cloud-storage",
        display_name="Cloud Storage",
        category=CAT_STORAGE,
        description="Object storage buckets.",
        icon="hard-drive",
        configuration_schema=[
            _region_field(),
            _f("location_type", "Location type", "select", default="single-region", required=False,
               group="Region / Location",
               options=_opts(("single-region", "Single-region"), ("dual-region", "Dual-region"), ("multi-region", "Multi-region")),
               help_text="Dual-/multi-region replicate data across locations at a higher $/GB."),

            _f("storage_class", "Storage class", "select", default="standard", required=False,
               group="Storage Class",
               options=_opts(("standard", "Standard"), ("nearline", "Nearline (30-day min)"),
                              ("coldline", "Coldline (90-day min)"), ("archive", "Archive (365-day min)"))),

            _f("stored_gb", "Total storage volume", unit="GB/month", default=0, group="Total Storage Volume"),

            _f("class_a_operations_per_month", "Class A operations (writes, list, create)", unit="ops/month", default=0,
               required=False, group="Data Operations Rate"),
            _f("class_b_operations_per_month", "Class B operations (reads, get)", unit="ops/month", default=0,
               required=False, group="Data Operations Rate"),

            _f("inter_region_transfer_gb_per_month", "Inter-region data transfer", unit="GB/month", default=0,
               required=False, group="Data Transfer"),
            _f("internet_egress_gb_per_month", "Internet egress", unit="GB/month", default=0,
               required=False, group="Data Transfer"),
        ],
        pricing_dimensions=[
            _d("storage", "Storage", "stored_gb", "GB/month", 0.020,
               rate_selector_field_id="storage_class",
               rate_by_option={"standard": 0.020, "nearline": 0.010, "coldline": 0.004, "archive": 0.0012}),
            _d("location-multiplier", "Dual-/multi-region storage premium", "stored_gb", "GB/month", 0.0,
               rate_selector_field_id="location_type",
               rate_by_option={"single-region": 0.0, "dual-region": 0.02, "multi-region": 0.026}),
            _d("class-a-ops", "Class A operations", "class_a_operations_per_month", "10,000 operations", 0.05, 10_000),
            _d("class-b-ops", "Class B operations", "class_b_operations_per_month", "10,000 operations", 0.004, 10_000),
            _d("inter-region-transfer", "Inter-region transfer", "inter_region_transfer_gb_per_month", "GB", 0.02),
            _d("internet-egress", "Internet egress", "internet_egress_gb_per_month", "GB", 0.12),
        ],
    ),
    GCPServiceDefinition(
        service_id="persistent-disk",
        display_name="Persistent Disk",
        category=CAT_STORAGE,
        description="Block storage attached to Compute Engine/GKE instances. Uses the project region selected above (Estimate details), not a per-card region.",
        icon="hard-drive",
        legacy_binding="storage",
        configuration_schema=[
            _f("disk_type", "Disk type", "select", default="pd-balanced", group="Disk Type",
               options=_opts(("pd-standard", "Standard HDD"), ("pd-balanced", "Balanced SSD"), ("pd-ssd", "Performance SSD"), ("pd-extreme", "Extreme PD"))),
            _f("size_gb", "Disk size", unit="GB", default=0, group="Disk Size"),

            _f("provisioned_iops", "Provisioned IOPS", default=0, min_value=0, required=False,
               group="Provisioned IOPS & Throughput",
               help_text="Extreme PD or custom SSD configurations only."),
            _f("provisioned_throughput_mbps", "Provisioned throughput", unit="MB/s", default=0, min_value=0, required=False,
               group="Provisioned IOPS & Throughput",
               help_text="Extreme PD or custom SSD configurations only."),

            _f("snapshot_enabled", "Enable snapshots", "boolean", default=False, required=False, group="Snapshot Storage"),
            _f("snapshot_retention_days", "Snapshot retention (days)", default=0, min_value=0, required=False, group="Snapshot Storage"),
            _f("snapshot_storage_gb", "Backup/snapshot storage stored", unit="GB/month", default=0, min_value=0, required=False,
               group="Snapshot Storage",
               help_text="If set, prices this directly instead of estimating from retention days."),

            _f("local_ssd_count", "Local SSD blocks (per instance)", unit="375 GB blocks", default=0, min_value=0, max_value=24, required=False),
        ],
    ),
    GCPServiceDefinition(
        service_id="filestore",
        display_name="Filestore",
        category=CAT_STORAGE,
        description="Managed NFS file storage.",
        icon="hard-drive",
        configuration_schema=[
            _region_field(),
            _f("tier", "Service tier", "select", default="basic-hdd", required=False, group="Service Tier",
               options=_opts(("basic-hdd", "Basic HDD"), ("basic-ssd", "Basic SSD"),
                              ("regional-ha", "Regional (High Availability)"), ("enterprise", "Enterprise"))),
            _f("capacity_gb", "Capacity", unit="GB/month", default=1024, group="Capacity",
               help_text="Minimum capacity applies: ~1024 GB for Basic/Regional/Enterprise, ~2560 GB for Basic SSD."),
        ],
        pricing_dimensions=[
            _d("capacity", "Capacity", "capacity_gb", "GB/month", 0.20,
               rate_selector_field_id="tier",
               rate_by_option={"basic-hdd": 0.20, "basic-ssd": 0.30, "regional-ha": 0.35, "enterprise": 0.60}),
        ],
    ),

    # -- Database -----------------------------------------------------------
    GCPServiceDefinition(
        service_id="cloud-sql",
        display_name="Cloud SQL",
        category=CAT_DATABASE,
        description="Managed relational database (PostgreSQL, MySQL, SQL Server). Uses the project region selected above (Estimate details), not a per-card region.",
        icon="database",
        legacy_binding="database",
        configuration_schema=[
            _f("engine", "Database engine", "select", default="postgres", group="Database Engine",
               options=_opts(("postgres", "PostgreSQL"), ("mysql", "MySQL"), ("sqlserver", "SQL Server"))),

            _f("high_availability", "High availability (Regional, multi-zone failover)", "boolean", default=False,
               required=False, group="High Availability"),

            _f("machine_tier", "Compute size", "select", default="custom", required=False, group="Compute Size",
               options=_opts(("shared-core", "Shared-core (db-f1-micro)"), ("custom", "Custom (vCPU + RAM)")),
               help_text="Shared-core ignores vCPU/RAM below and uses a flat db-f1-micro rate."),
            _f("vcpu", "vCPU", default=0, group="Compute Size"),
            _f("ram_gb", "RAM", unit="GB", default=0, group="Compute Size"),

            _f("storage_type", "Storage type", "select", default="ssd", required=False, group="Storage",
               options=_opts(("hdd", "HDD"), ("ssd", "SSD"))),
            _f("size_gb", "Storage capacity", unit="GB", default=0, min_value=0, group="Storage"),

            _f("backup_storage_gb", "Retained backup storage", unit="GB/month", default=0, min_value=0,
               required=False, group="Backups & Logs"),
            _f("binary_log_storage_gb", "Binary log storage", unit="GB/month", default=0, min_value=0,
               required=False, group="Backups & Logs"),

            _f("commitment", "Commitment", "select", default="none", required=False, group="Commitments",
               options=_opts(("none", "None (on-demand)"), ("1-year", "1-Year Committed Use Discount"), ("3-year", "3-Year Committed Use Discount"))),
        ],
    ),
    GCPServiceDefinition(
        service_id="alloydb",
        display_name="AlloyDB",
        category=CAT_DATABASE,
        description="PostgreSQL-compatible database for demanding enterprise workloads.",
        icon="database",
        configuration_schema=[
            _region_field(),

            _f("vcpu", "Primary instance vCPU", unit="vCPU", default=0, group="Instance Nodes"),
            _f("ram_gb", "Primary instance RAM", unit="GB", default=0, required=False, group="Instance Nodes",
               help_text="Leave blank to use AlloyDB's standard 8 GB/vCPU ratio."),
            _f("read_pool_nodes", "Read pool nodes", default=0, min_value=0, required=False, group="Instance Nodes"),
            _f("read_pool_vcpu_per_node", "vCPU per read pool node", unit="vCPU", default=0, min_value=0,
               required=False, group="Instance Nodes"),

            _f("storage_gb", "Cluster storage (auto-scaled)", unit="GB", default=0, group="Cluster Storage"),

            _f("backup_storage_gb", "Retained backup storage", unit="GB/month", default=0, min_value=0,
               required=False, group="Backup Storage"),
        ],
        pricing_dimensions=[
            _d("vcpu", "Primary instance vCPU", "vcpu", "vCPU/month", 109.0),
            _d("ram", "Primary instance RAM", "ram_gb", "GB/month", 18.26),
            _d("storage", "Cluster storage", "storage_gb", "GB/month", 0.0004),
            _d("read-pool-nodes", "Read pool nodes", "read_pool_nodes", "node/month", 218.0),
            _d("read-pool-vcpu", "Read pool vCPU (nodes x vCPU/node)", "read_pool_total_vcpu", "vCPU/month", 109.0),
            _d("backup-storage", "Backup storage", "backup_storage_gb", "GB/month", 0.10),
        ],
    ),
    GCPServiceDefinition(
        service_id="spanner",
        display_name="Spanner",
        category=CAT_DATABASE,
        description="Globally distributed, horizontally scalable relational database.",
        icon="database",
        configuration_schema=[
            _f("deployment_type", "Deployment type", "select", default="regional", required=False,
               group="Deployment Type",
               options=_opts(("regional", "Regional"), ("multi-region", "Multi-Region"))),
            _region_field(group="Deployment Type"),

            _f("capacity_mode", "Provisioned compute mode", "select", default="processing_units", required=False,
               group="Provisioned Compute",
               options=_opts(("processing_units", "Processing units"), ("nodes", "Nodes"))),
            _f("processing_units", "Processing units", default=100, min_value=100, group="Provisioned Compute",
               help_text="Used when mode = Processing units (100-1,000 PU granularity)."),
            _f("node_count", "Nodes", default=0, min_value=0, required=False, group="Provisioned Compute",
               help_text="Used when mode = Nodes. 1 node = 1,000 processing units."),

            _f("storage_gb", "Database storage", unit="GB", default=0, group="Database Storage"),
            _f("backup_storage_gb", "Backup storage", unit="GB/month", default=0, min_value=0, required=False, group="Backup Storage"),
        ],
        pricing_dimensions=[
            _d("compute", "Compute capacity", "processing_units", "100 processing units/month", 65.0, 100,
               rate_selector_field_id="deployment_type",
               rate_by_option={"regional": 65.0, "multi-region": 195.0}),
            _d("storage", "Storage", "storage_gb", "GB/month", 0.30),
            _d("backup-storage", "Backup storage", "backup_storage_gb", "GB/month", 0.30),
        ],
    ),
    GCPServiceDefinition(
        service_id="firestore",
        display_name="Firestore",
        category=CAT_DATABASE,
        description="Serverless document database.",
        icon="database",
        configuration_schema=[
            _f("mode", "Mode", "select", default="native", required=False, group="Mode",
               options=_opts(("native", "Native mode"), ("datastore", "Datastore mode")),
               help_text="Informational - both modes are priced identically on Google Cloud."),

            _f("stored_gb", "Database storage", unit="GB", default=0, group="Database Storage"),

            _f("reads_per_month", "Document reads", unit="reads/month", default=0, group="Document Operations"),
            _f("writes_per_month", "Document writes", unit="writes/month", default=0, group="Document Operations"),
            _f("deletes_per_month", "Document deletes", unit="deletes/month", default=0, required=False, group="Document Operations"),

            _f("egress_gb_per_month", "Network egress", unit="GB/month", default=0, required=False, group="Network Egress"),
        ],
        pricing_dimensions=[
            _d("storage", "Storage", "stored_gb", "GB/month", 0.18),
            _d("reads", "Reads", "reads_per_month", "100,000 reads", 0.06, 100_000),
            _d("writes", "Writes", "writes_per_month", "100,000 writes", 0.18, 100_000),
            _d("deletes", "Deletes", "deletes_per_month", "100,000 deletes", 0.02, 100_000),
            _d("egress", "Network egress", "egress_gb_per_month", "GB", 0.12),
        ],
    ),
    GCPServiceDefinition(
        service_id="bigtable",
        display_name="Bigtable",
        category=CAT_DATABASE,
        description="Wide-column NoSQL database for large analytical/operational workloads.",
        icon="database",
        configuration_schema=[
            _region_field(),
            _f("storage_type", "Storage type", "select", default="ssd", required=False, group="Storage Type",
               options=_opts(("ssd", "SSD"), ("hdd", "HDD"))),
            _f("nodes", "Cluster nodes", default=1, min_value=1, group="Cluster Nodes"),
            _f("storage_gb", "Storage capacity", unit="GB", default=0, group="Storage Capacity"),
        ],
        pricing_dimensions=[
            _d("nodes", "Nodes", "nodes", "node/month", 468.0),
            _d("storage", "Storage", "storage_gb", "GB/month", 0.17,
               rate_selector_field_id="storage_type",
               rate_by_option={"ssd": 0.17, "hdd": 0.026}),
        ],
    ),
    GCPServiceDefinition(
        service_id="memorystore",
        display_name="Memorystore",
        category=CAT_DATABASE,
        description="Managed Redis/Memcached in-memory cache.",
        icon="database",
        configuration_schema=[
            _region_field(),
            _f("tier", "Service tier", "select", default="standard-ha", required=False, group="Service Tier",
               options=_opts(("basic", "Basic (standalone)"), ("standard-ha", "Standard (HA with replica)"))),
            _f("capacity_gb", "Capacity", unit="GB", default=0, group="Capacity Tier"),
        ],
        pricing_dimensions=[
            _d("capacity", "Capacity", "capacity_gb", "GB/month", 49.0,
               rate_selector_field_id="tier",
               rate_by_option={"basic": 35.0, "standard-ha": 49.0}),
        ],
    ),

    # -- Networking -----------------------------------------------------
    GCPServiceDefinition(
        service_id="vpc",
        display_name="VPC",
        category=CAT_NETWORKING,
        description="Virtual private cloud network and subnets.",
        icon="network",
        configuration_schema=[
            _f("subnets", "Subnets", default=1, min_value=1, required=False),
            _f("static_ips", "Reserved static IPs", default=0, min_value=0, required=False),
            _f("intra_region_egress_gb_per_month", "Intra-region egress (GB/month)", unit="GB", default=0,
               required=False, group="Egress",
               help_text="Traffic between different zones in the same region."),
            _f("inter_region_egress_gb_per_month", "Inter-region egress (GB/month)", unit="GB", default=0,
               required=False, group="Egress",
               help_text="Traffic between different GCP regions."),
        ],
        pricing_dimensions=[
            _d("static-ips", "Reserved static IPs", "static_ips", "IP/month", 7.30),
            _d("intra-region-egress", "Intra-region egress", "intra_region_egress_gb_per_month", "GB", 0.01),
            _d("inter-region-egress", "Inter-region egress", "inter_region_egress_gb_per_month", "GB", 0.02),
        ],
    ),
    GCPServiceDefinition(
        service_id="load-balancing",
        display_name="Load Balancing",
        category=CAT_NETWORKING,
        description="Global External HTTP(S), Regional HTTP(S), Network Passthrough, or Internal load balancing.",
        icon="network",
        configuration_schema=[
            _f("lb_type", "Load balancer type", "select", default="global_https", group="Load Balancer Type",
               options=_opts(("global_https", "Global External HTTP(S)"), ("regional_https", "Regional HTTP(S)"),
                              ("network_passthrough", "Network Passthrough"), ("internal", "Internal")),
               help_text="Global/Regional HTTP(S) LBs carry a monthly forwarding-rule base fee; Passthrough/Internal do not."),
            _f("forwarding_rules", "Forwarding rules", default=1, min_value=0, required=False, group="Forwarding Rules"),
            _f("processed_data_gb_per_month", "Processed data (GB/month)", unit="GB", default=0, required=False,
               group="Processed Data", help_text="Inbound + outbound data processed by the load balancer."),
        ],
        pricing_dimensions=[
            _d("base-fee", "Base fee", "_unit_flag", "month", 0.0,
               rate_selector_field_id="lb_type",
               rate_by_option={"global_https": 18.26, "regional_https": 18.26, "network_passthrough": 0.0, "internal": 0.0}),
            _d("forwarding-rules", "Forwarding rules", "forwarding_rules", "rule/month", 18.26),
            _d("processed-data", "Processed data", "processed_data_gb_per_month", "GB", 0.008,
               rate_selector_field_id="lb_type",
               rate_by_option={"global_https": 0.008, "regional_https": 0.008, "network_passthrough": 0.004, "internal": 0.004}),
        ],
    ),
    GCPServiceDefinition(
        service_id="cloud-nat",
        display_name="Cloud NAT",
        category=CAT_NETWORKING,
        description="Managed network address translation for outbound traffic.",
        icon="network",
        configuration_schema=[
            _region_field(),
            _f("gateways", "Gateways", default=1, min_value=1),
            _f("data_processed_gb_per_month", "Data processed (GB/month)", unit="GB", default=0),
        ],
        pricing_dimensions=[
            _d("gateways", "Gateways", "gateways", "gateway/month", 32.85),
            _d("data-processed", "Data processed", "data_processed_gb_per_month", "GB", 0.045),
        ],
    ),
    GCPServiceDefinition(
        service_id="cloud-cdn",
        display_name="Cloud CDN",
        category=CAT_NETWORKING,
        description="Content delivery network in front of your load balancer.",
        icon="network",
        configuration_schema=[
            _f("cache_egress_gb_per_month", "Cache egress (GB/month)", unit="GB", default=0, required=False,
               group="Cache Egress", help_text="Outbound traffic served from cache to clients."),
            _f("invalidation_requests_per_month", "Cache invalidation requests/month", default=0, required=False,
               group="Cache Invalidation"),
            _f("cache_lookup_requests_per_month", "HTTP/HTTPS cache lookup requests/month", default=0, required=False,
               group="Cache Lookup Requests"),
        ],
        pricing_dimensions=[
            _d("cache-egress", "Cache egress", "cache_egress_gb_per_month", "GB", 0.08),
            _d("invalidation-requests", "Cache invalidation requests", "invalidation_requests_per_month", "request", 0.005),
            _d("cache-lookup-requests", "Cache lookup requests", "cache_lookup_requests_per_month", "10,000 requests", 0.075, 10_000),
        ],
    ),
    GCPServiceDefinition(
        service_id="cloud-armor",
        display_name="Cloud Armor",
        category=CAT_NETWORKING,
        description="DDoS protection and web application firewall.",
        icon="shield",
        configuration_schema=[
            _f("policy_type", "Policy type", "select", default="standard", required=False, group="Policy Type",
               options=_opts(("standard", "Standard"), ("managed_plus", "Managed Protection Plus"))),
            _f("policies", "Security policies", default=1, min_value=1, group="Rule Count"),
            _f("rule_count", "Rules configured", default=0, min_value=0, required=False, group="Rule Count"),
            _f("requests_per_month", "Requests inspected/month", default=0, group="Request Volume"),
        ],
        pricing_dimensions=[
            _d("policies", "Policies", "policies", "policy/month", 5.0),
            _d("rules", "Rules configured", "rule_count", "rule/month", 1.0),
            _d("requests", "Requests inspected", "requests_per_month", "million requests", 0.75, 1_000_000),
            _d("managed-plus-fee", "Managed Protection Plus subscription", "_unit_flag", "month", 0.0,
               rate_selector_field_id="policy_type", rate_by_option={"standard": 0.0, "managed_plus": 3000.0}),
        ],
    ),
    GCPServiceDefinition(
        service_id="cloud-dns",
        display_name="Cloud DNS",
        category=CAT_NETWORKING,
        description="Managed authoritative DNS.",
        icon="network",
        configuration_schema=[
            _f("zone_type", "Zone type", "select", default="public", required=False, group="Managed Zones",
               options=_opts(("public", "Public"), ("private", "Private")),
               help_text="Informational - Google Cloud prices public and private zones identically."),
            _f("managed_zones", "Managed zones", default=1, min_value=1, group="Managed Zones"),
            _f("queries_per_month", "Queries/month", default=0, group="DNS Queries"),
        ],
        pricing_dimensions=[
            _d("zones", "Managed zones", "managed_zones", "zone/month", 0.20),
            _d("queries", "Queries", "queries_per_month", "million queries", 0.40, 1_000_000),
        ],
    ),
    GCPServiceDefinition(
        service_id="vpn",
        display_name="VPN",
        category=CAT_NETWORKING,
        description="Cloud VPN tunnels to on-premises or other clouds.",
        icon="network",
        configuration_schema=[
            _f("vpn_type", "VPN type", "select", default="ha", required=False, group="VPN Type",
               options=_opts(("classic", "Classic VPN"), ("ha", "HA VPN")),
               help_text="HA VPN needs redundant tunnel pairs for its 99.99% SLA - count both in Tunnels below."),
            _f("tunnels", "Tunnels", default=1, min_value=1, required=False, group="Tunnel Count"),
            _f("data_egress_gb_per_month", "Data egress (GB/month)", unit="GB", default=0, required=False,
               group="Data Egress"),
        ],
        pricing_dimensions=[
            _d("tunnels", "Tunnels", "tunnels", "tunnel/month", 36.50,
               rate_selector_field_id="vpn_type", rate_by_option={"classic": 36.50, "ha": 36.50}),
            _d("data-egress", "Data egress", "data_egress_gb_per_month", "GB", 0.09),
        ],
    ),
    GCPServiceDefinition(
        service_id="interconnect",
        display_name="Interconnect",
        category=CAT_NETWORKING,
        description="Dedicated or partner Interconnect to Google's network.",
        icon="network",
        configuration_schema=[
            _f("connection_type", "Connection type", "select", default="dedicated", group="Connection Type",
               options=_opts(("dedicated", "Dedicated Interconnect"), ("partner", "Partner Interconnect"))),
            _f("capacity", "Capacity / port speed", "select", default="10gbps", group="Capacity / Port Speed",
               options=_opts(("50mbps", "50 Mbps"), ("100mbps", "100 Mbps"), ("200mbps", "200 Mbps"),
                              ("500mbps", "500 Mbps"), ("1gbps", "1 Gbps"), ("2gbps", "2 Gbps"),
                              ("5gbps", "5 Gbps"), ("10gbps", "10 Gbps"), ("100gbps", "100 Gbps")),
               help_text="Dedicated ports come in 10/100 Gbps; Partner Interconnect ranges from 50 Mbps to 10 Gbps."),
            _f("connections", "Connections", default=1, min_value=1, group="Connection Type"),
            _f("outbound_egress_gb_per_month", "Outbound egress (GB/month)", unit="GB", default=0, required=False,
               group="Outbound Egress Volume"),
        ],
        pricing_dimensions=[
            _d("connection-type-fee", "Connection base fee", "connections", "connection/month", 1700.0,
               rate_selector_field_id="connection_type", rate_by_option={"dedicated": 1700.0, "partner": 300.0}),
            _d("capacity-surcharge", "Capacity surcharge", "connections", "connection/month", 0.0,
               rate_selector_field_id="capacity",
               rate_by_option={"50mbps": 0.0, "100mbps": 50.0, "200mbps": 150.0, "500mbps": 400.0,
                                "1gbps": 800.0, "2gbps": 1600.0, "5gbps": 4000.0, "10gbps": 8000.0, "100gbps": 80000.0}),
            _d("outbound-egress", "Outbound egress", "outbound_egress_gb_per_month", "GB", 0.03),
        ],
    ),
    GCPServiceDefinition(
        service_id="network-egress",
        display_name="Network egress",
        category=CAT_NETWORKING,
        description="Internet egress bandwidth not tied to a specific service.",
        icon="network",
        configuration_schema=[
            _f("destination_tier", "Destination tier", "select", default="premium", group="Destination Tier",
               options=_opts(("standard", "Standard Tier"), ("premium", "Premium Tier"))),
            _region_field(group="Destination Region"),
            _f("estimated_egress_gb_per_month", "Estimated egress (GB/month)", unit="GB", default=0,
               group="Destination Region"),
        ],
        pricing_dimensions=[
            _d("egress", "Internet egress", "estimated_egress_gb_per_month", "GB", 0.12,
               rate_selector_field_id="destination_tier", rate_by_option={"standard": 0.085, "premium": 0.12}),
        ],
    ),

    # -- Messaging & Eventing --------------------------------------------
    GCPServiceDefinition(
        service_id="pubsub",
        display_name="Pub/Sub",
        category=CAT_MESSAGING,
        description="Asynchronous messaging between services.",
        icon="send",
        # Priced by MessagingObservabilityPricingCalculator (data-volume +
        # documented free tier, matching Google's actual Pub/Sub billing
        # model), not by GenericServicePricingCalculator - see
        # app/catalog/messaging_observability_pricing.py. pricing_dimensions
        # is intentionally empty; this schema mirrors the FinOps team's
        # "PUB/SUB costing: New configuration" worksheet field-for-field.
        configuration_schema=[
            _f("published_data_gb_per_day", "Amount of published data daily (GB)", unit="GB/day", default=0),
            _f("delivery_type", "Message delivery type", "select", default="basic",
               options=_opts(("basic", "Basic"), ("bigquery", "BigQuery")), required=False),
            _f("topic_retention_days", "Topic retention (days)", default=0, min_value=0, max_value=31, required=False,
               help_text="Beyond the free 7-day default, extra retention adds storage cost (not yet priced here)."),
            _f("subscriptions", "Number of subscriptions", default=0, min_value=0, required=False),
            _f("subscriptions_with_retained_acks", "Subscriptions with retained acknowledged messages", default=0, min_value=0, required=False,
               help_text="Storage cost for retained/replayable messages is not yet priced here."),
            _f("ack_retention_window_days", "Average retention window (days)", default=0, min_value=0, max_value=7, required=False),
            _f("snapshots_per_month", "Number of snapshots used per month", default=0, min_value=0, required=False,
               help_text="Snapshot storage cost is not yet priced here."),
            _f("snapshot_retention_days", "Snapshot average retention window (days)", default=0, min_value=0, required=False),
        ],
        pricing_dimensions=[],
    ),
    GCPServiceDefinition(
        service_id="eventarc",
        display_name="Eventarc",
        category=CAT_MESSAGING,
        description="Event routing between GCP services.",
        icon="send",
        configuration_schema=[_f("events_per_month", "Events/month", default=0)],
        pricing_dimensions=[_d("events", "Events", "events_per_month", "million events", 10.0, 1_000_000)],
    ),
    GCPServiceDefinition(
        service_id="cloud-tasks",
        display_name="Cloud Tasks",
        category=CAT_MESSAGING,
        description="Managed task queues for asynchronous work.",
        icon="send",
        configuration_schema=[_f("tasks_per_month", "Tasks/month", default=0)],
        pricing_dimensions=[_d("tasks", "Tasks", "tasks_per_month", "million tasks", 0.40, 1_000_000)],
    ),
    GCPServiceDefinition(
        service_id="cloud-scheduler",
        display_name="Cloud Scheduler",
        category=CAT_MESSAGING,
        description="Managed cron job scheduler.",
        icon="send",
        configuration_schema=[_f("jobs", "Scheduled jobs", default=1, min_value=1)],
        pricing_dimensions=[_d("jobs", "Jobs", "jobs", "job/month", 0.10)],
    ),
    GCPServiceDefinition(
        service_id="workflows",
        display_name="Workflows",
        category=CAT_MESSAGING,
        description="Serverless workflow orchestration.",
        icon="send",
        configuration_schema=[
            _f("executions_per_month", "Executions/month", default=0),
            _f("steps_per_execution", "Steps per execution", default=0, required=False),
        ],
        pricing_dimensions=[_d("executions", "Executions", "executions_per_month", "1,000 executions", 0.025, 1_000)],
    ),

    # -- Analytics & Data -------------------------------------------------
    GCPServiceDefinition(
        service_id="bigquery",
        display_name="BigQuery",
        category=CAT_ANALYTICS,
        description="Serverless data warehouse.",
        icon="bar-chart",
        configuration_schema=[
            _f("pricing_model", "Pricing model", "select", default="on_demand", required=False, group="Pricing Model",
               options=_opts(("on_demand", "On-Demand"), ("standard_edition", "Standard Edition"),
                              ("enterprise_edition", "Enterprise Edition"), ("enterprise_plus_edition", "Enterprise Plus Edition")),
               help_text="On-Demand prices by TB scanned below; Editions price by slots provisioned below - fill in only the side that applies."),
            _f("tb_scanned_per_month", "Data scanned (TB/month)", unit="TB", default=0, required=False, group="Query Usage - On-Demand"),
            _f("slots_provisioned", "Slots provisioned (vCPUs)", default=0, min_value=0, required=False, group="Query Usage - Editions"),
            _f("commitment", "Commitment duration", "select", default="none", required=False, group="Query Usage - Editions",
               options=_opts(("none", "None"), ("1-year", "1-Year"), ("3-year", "3-Year")),
               help_text="Informational - commitment discounts aren't reflected in this indicative estimate."),
            _f("active_storage_gb", "Active storage (GB)", unit="GB", default=0, required=False, group="Storage Volume"),
            _f("long_term_storage_gb", "Long-term storage, >90 days unedited (GB)", unit="GB", default=0,
               required=False, group="Storage Volume"),
            _f("streaming_inserts_gb_per_month", "Streaming inserts & CDC (GB/month)", unit="GB", default=0,
               required=False, group="Streaming Inserts & CDC"),
        ],
        pricing_dimensions=[
            _d("query", "On-demand queries", "tb_scanned_per_month", "TB scanned", 6.25),
            _d("slots", "Provisioned slots", "slots_provisioned", "slot/month", 0.0,
               rate_selector_field_id="pricing_model",
               rate_by_option={"on_demand": 0.0, "standard_edition": 29.20, "enterprise_edition": 43.80, "enterprise_plus_edition": 73.00}),
            _d("storage", "Active storage", "active_storage_gb", "GB/month", 0.02),
            _d("long-term-storage", "Long-term storage", "long_term_storage_gb", "GB/month", 0.01),
            _d("streaming-inserts", "Streaming inserts & CDC", "streaming_inserts_gb_per_month", "GB", 0.05),
        ],
    ),
    GCPServiceDefinition(
        service_id="dataflow",
        display_name="Dataflow",
        category=CAT_ANALYTICS,
        description="Managed stream/batch data processing (Apache Beam).",
        icon="bar-chart",
        configuration_schema=[
            _f("workload_type", "Workload type", "select", default="batch", required=False, group="Workload Type",
               options=_opts(("streaming", "Streaming"), ("batch", "Batch"))),
            _f("vcpu_hours_per_month", "Worker vCPU-hours/month", unit="vCPU-hr", default=0, group="Compute Resources"),
            _f("ram_gb_hours_per_month", "Worker RAM GiB-hours/month", unit="GiB-hr", default=0, required=False, group="Compute Resources"),
            _f("worker_disk_gb", "Persistent disk per worker (GB)", unit="GB", default=0, required=False, group="Storage & Processing"),
            _f("processed_data_gb_per_month", "Data processed (GB/month)", unit="GB", default=0, required=False, group="Storage & Processing"),
        ],
        pricing_dimensions=[
            _d("vcpu-hours", "vCPU hours", "vcpu_hours_per_month", "vCPU-hour", 0.056,
               rate_selector_field_id="workload_type", rate_by_option={"streaming": 0.069, "batch": 0.056}),
            _d("ram-gib-hours", "RAM GiB-hours", "ram_gb_hours_per_month", "GiB-hour", 0.0035),
            _d("worker-disk", "Worker persistent disk", "worker_disk_gb", "GB/month", 0.04),
            _d("processed-data", "Data processed", "processed_data_gb_per_month", "GB", 0.01),
        ],
    ),
    GCPServiceDefinition(
        service_id="dataproc",
        display_name="Dataproc",
        category=CAT_ANALYTICS,
        description="Managed Spark/Hadoop clusters.",
        icon="bar-chart",
        configuration_schema=[
            _f("node_vcpu", "vCPU per node", unit="vCPU", default=0, min_value=0, group="Cluster Provisioning"),
            _f("node_ram_gb", "RAM per node", unit="GB", default=0, min_value=0, required=False, group="Cluster Provisioning",
               help_text="Informational - Dataproc's management premium is billed per vCPU-hour only; RAM affects the underlying VM cost, not modeled here."),
            _f("node_count", "Node count", default=0, min_value=0, group="Cluster Provisioning"),
            _f("cluster_hours_per_month", "Cluster running hours/month", unit="hr", default=0, group="Execution Metrics"),
        ],
        pricing_dimensions=[_d("vcpu-hours", "vCPU hours (management premium)", "vcpu_hours_per_month", "vCPU-hour", 0.01)],
    ),
    GCPServiceDefinition(
        service_id="data-fusion",
        display_name="Data Fusion",
        category=CAT_ANALYTICS,
        description="Managed, code-free data integration service.",
        icon="bar-chart",
        configuration_schema=[
            _f("edition", "Edition", "select", default="enterprise", required=False, group="Edition",
               options=_opts(("basic", "Basic"), ("enterprise", "Enterprise"))),
            _f("instance_hours_per_month", "Instance hours/month", unit="hr", default=0, group="Instance Hours",
               help_text="Uptime of the Data Fusion control plane."),
            _f("pipeline_execution_vcpu_hours_per_month", "Pipeline execution vCPU-hours/month", unit="vCPU-hr", default=0,
               required=False, group="Pipeline Execution",
               help_text="Approximates the underlying ephemeral Dataproc cluster execution cost."),
        ],
        pricing_dimensions=[
            _d("instance-hours", "Instance hours", "instance_hours_per_month", "hour", 3.15,
               rate_selector_field_id="edition", rate_by_option={"basic": 0.90, "enterprise": 3.15}),
            _d("pipeline-execution", "Pipeline execution", "pipeline_execution_vcpu_hours_per_month", "vCPU-hour", 0.07),
        ],
    ),
    GCPServiceDefinition(
        service_id="datastream",
        display_name="Datastream",
        category=CAT_ANALYTICS,
        description="Serverless change data capture and replication.",
        icon="bar-chart",
        configuration_schema=[_f("gb_processed_per_month", "CDC ingestion volume (GB/month)", unit="GB", default=0)],
        pricing_dimensions=[_d("data-processed", "Data processed", "gb_processed_per_month", "GB", 0.10)],
    ),
    GCPServiceDefinition(
        service_id="composer",
        display_name="Composer",
        category=CAT_ANALYTICS,
        description="Managed Apache Airflow workflow orchestration.",
        icon="bar-chart",
        configuration_schema=[
            _f("environment_size", "Environment size", "select", default="small", required=False, group="Environment Size",
               options=_opts(("small", "Small"), ("medium", "Medium"), ("large", "Large"), ("custom", "Custom"))),
            _f("vcpu_hours_per_month", "Environment CPU vCPU-hours/month", unit="vCPU-hr", default=0, group="Environment Resources"),
            _f("sql_storage_gb", "Airflow metadata DB storage (GB)", unit="GB", default=0, required=False, group="Environment Resources"),
            _f("environment_ram_gb_hours_per_month", "Environment RAM GiB-hours/month", unit="GiB-hr", default=0,
               required=False, group="Environment Resources"),
            _f("worker_min_count", "Worker minimum count", default=1, min_value=0, required=False, group="Worker Scaling Limits",
               help_text="Informational sizing input - cost is captured by the resource dimensions above."),
            _f("worker_max_count", "Worker maximum count", default=3, min_value=0, required=False, group="Worker Scaling Limits"),
        ],
        pricing_dimensions=[
            _d("vcpu-hours", "Environment CPU", "vcpu_hours_per_month", "vCPU-hour", 0.07,
               rate_selector_field_id="environment_size",
               rate_by_option={"small": 0.05, "medium": 0.07, "large": 0.10, "custom": 0.07}),
            _d("sql-storage", "Airflow metadata DB storage", "sql_storage_gb", "GB/month", 0.17),
            _d("ram-gib-hours", "Environment RAM", "environment_ram_gb_hours_per_month", "GiB-hour", 0.0035),
        ],
    ),

    # -- AI / ML ------------------------------------------------------------
    GCPServiceDefinition(
        service_id="vertex-ai",
        display_name="Vertex AI",
        category=CAT_AI_ML,
        description="Managed ML platform - generative AI, custom training, online prediction, and endpoint hosting.",
        icon="brain",
        configuration_schema=[
            _f("prediction_requests_per_month", "Prediction requests/month", default=0, group="Online Predictions"),
            _f("input_tokens_millions_per_month", "Prompt / input tokens (millions/month)", unit="M tokens",
               default=0, required=False, group="Generative AI (Gemini)"),
            _f("output_tokens_millions_per_month", "Output tokens (millions/month)", unit="M tokens",
               default=0, required=False, group="Generative AI (Gemini)"),
            _f("training_vm_machine_type", "Training VM machine type", "select", default="n1-standard-4",
               required=False, group="Custom Training",
               options=_opts(("n1-standard-4", "n1-standard-4"), ("n1-highmem-8", "n1-highmem-8"),
                              ("a2-highgpu-1g", "a2-highgpu-1g (GPU)"), ("a3-highgpu-8g", "a3-highgpu-8g (GPU)"))),
            _f("training_hours_per_month", "GPU/TPU training hours/month", unit="hr", default=0, required=False,
               group="Custom Training"),
            _f("endpoint_node_hours_per_month", "Deployed endpoint node-hours/month", unit="node-hr", default=0,
               required=False, group="Endpoint Hosting",
               help_text="Number of node-hours across all deployed prediction endpoints."),
            _f("search_tier", "Search tier", "select", default="standard", required=False,
               options=_opts(("standard", "Standard"), ("advanced", "Advanced")),
               group="Vector Index & Search Queries"),
            _f("vector_search_queries_per_month", "Standard/advanced search queries/month", default=0,
               required=False, group="Vector Index & Search Queries"),
        ],
        pricing_dimensions=[
            _d("predictions", "Predictions", "prediction_requests_per_month", "million requests", 6.0, 1_000_000),
            _d("gemini-input-tokens", "Gemini input tokens", "input_tokens_millions_per_month", "million tokens", 0.15),
            _d("gemini-output-tokens", "Gemini output tokens", "output_tokens_millions_per_month", "million tokens", 0.60),
            _d("training", "Custom training", "training_hours_per_month", "hour", 2.5,
               rate_selector_field_id="training_vm_machine_type",
               rate_by_option={"n1-standard-4": 0.19, "n1-highmem-8": 0.474,
                                "a2-highgpu-1g": 3.67, "a3-highgpu-8g": 28.0}),
            _d("endpoint-hosting", "Endpoint hosting", "endpoint_node_hours_per_month", "node-hour", 0.20),
            _d("vector-search-queries", "Vector index search queries", "vector_search_queries_per_month",
               "1,000 queries", 0.05, 1_000, rate_selector_field_id="search_tier",
               rate_by_option={"standard": 0.03, "advanced": 0.08}),
        ],
    ),
    GCPServiceDefinition(
        service_id="genai-model-costing",
        display_name="Generative AI Models (Gemini / Claude / GPT)",
        category=CAT_AI_ML,
        description=(
            "Per-token cost of calling a hosted large language model through Vertex AI: Google's Gemini, "
            "Anthropic's Claude (via Vertex AI Model Garden), and OpenAI's open-weight gpt-oss models (via "
            "Vertex AI Model Garden serverless MaaS endpoints). Separate from the Vertex AI card above, which "
            "covers custom training, endpoint hosting, and vector search instead of model token usage."
        ),
        icon="brain",
        configuration_schema=[
            _f("model", "Model", "select", default="gemini-2.5-flash", group="Model",
               options=_opts(
                   ("gemini-2.5-pro", "Gemini 2.5 Pro (Google)"),
                   ("gemini-2.5-flash", "Gemini 2.5 Flash (Google)"),
                   ("gemini-2.5-flash-lite", "Gemini 2.5 Flash-Lite (Google)"),
                   ("claude-opus-4.5", "Claude Opus 4.5 (Anthropic, Model Garden)"),
                   ("claude-sonnet-4.5", "Claude Sonnet 4.5 (Anthropic, Model Garden)"),
                   ("claude-haiku-4.5", "Claude Haiku 4.5 (Anthropic, Model Garden)"),
                   ("gpt-oss-120b", "gpt-oss-120b (OpenAI, Model Garden)"),
                   ("gpt-oss-20b", "gpt-oss-20b (OpenAI, Model Garden)"),
               ),
               help_text="Each model has its own input/output token price - selecting it here drives both dimensions below."),
            _f("model_region", "Region", "select", default="us-central1", group="Model",
               options=_opts(
                   ("us-central1", "us-central1 (Iowa)"),
                   ("us-east5", "us-east5 (Columbus)"),
                   ("europe-west1", "europe-west1 (Belgium)"),
                   ("europe-west4", "europe-west4 (Netherlands)"),
                   ("asia-southeast1", "asia-southeast1 (Singapore)"),
                   ("global", "global (Gemini global endpoint)"),
               ),
               help_text=(
                   "Vertex AI requires a region (or the 'global' endpoint) to call a model, and Model Garden "
                   "partner models are only available in a subset of regions - this doesn't change the price "
                   "shown (list price is uniform per model), only where you're allowed to call it from."
               )),
            _f("input_tokens_millions_per_month", "Input (prompt) tokens - millions/month", unit="M tokens",
               default=0, group="Monthly Token Volume"),
            _f("output_tokens_millions_per_month", "Output (completion) tokens - millions/month", unit="M tokens",
               default=0, group="Monthly Token Volume"),
        ],
        pricing_dimensions=[
            _d("model-input-tokens", "Input tokens", "input_tokens_millions_per_month", "million tokens", 0.30,
               rate_selector_field_id="model", rate_by_option={
                   "gemini-2.5-pro": 1.25, "gemini-2.5-flash": 0.30, "gemini-2.5-flash-lite": 0.10,
                   "claude-opus-4.5": 5.00, "claude-sonnet-4.5": 3.00, "claude-haiku-4.5": 1.00,
                   "gpt-oss-120b": 0.15, "gpt-oss-20b": 0.05,
               }),
            _d("model-output-tokens", "Output tokens", "output_tokens_millions_per_month", "million tokens", 2.50,
               rate_selector_field_id="model", rate_by_option={
                   "gemini-2.5-pro": 10.00, "gemini-2.5-flash": 2.50, "gemini-2.5-flash-lite": 0.40,
                   "claude-opus-4.5": 25.00, "claude-sonnet-4.5": 15.00, "claude-haiku-4.5": 5.00,
                   "gpt-oss-120b": 0.60, "gpt-oss-20b": 0.20,
               }),
        ],
    ),
    GCPServiceDefinition(
        service_id="gpu",
        display_name="GPU",
        category=CAT_AI_ML,
        description="Standalone GPU accelerators attached to a workload (outside Compute Engine sizing).",
        icon="cpu",
        configuration_schema=[
            _f("gpu_type", "GPU model", "select", default="nvidia-l4", group="GPU (Hardware Accelerator)",
               options=_opts(("nvidia-tesla-t4", "NVIDIA T4"), ("nvidia-l4", "NVIDIA L4"),
                              ("nvidia-tesla-a100", "NVIDIA A100"), ("nvidia-h100-80gb", "NVIDIA H100"),
                              ("nvidia-tesla-v100", "NVIDIA V100")),
               required=False),
            _f("gpu_count", "GPUs per host", unit="GPUs", default=1, min_value=1, group="GPU (Hardware Accelerator)"),
            _f("gpu_hours_per_month", "Execution time (hours/month)", unit="GPU-hr", default=0,
               group="GPU (Hardware Accelerator)",
               help_text="Hours each GPU runs per month; multiplied by GPU count for total billable GPU-hours."),
        ],
        pricing_dimensions=[
            _d("gpu-hours", "GPU hours", "gpu_hours_total_per_month", "GPU-hour", 0.55,
               rate_selector_field_id="gpu_type",
               rate_by_option={"nvidia-tesla-t4": 0.35, "nvidia-l4": 0.55, "nvidia-tesla-a100": 2.90,
                                "nvidia-h100-80gb": 5.80, "nvidia-tesla-v100": 1.10}),
        ],
    ),
    GCPServiceDefinition(
        service_id="tpu",
        display_name="TPU",
        category=CAT_AI_ML,
        description="Tensor Processing Units for large-scale ML training/inference.",
        icon="cpu",
        configuration_schema=[
            _f("tpu_type", "TPU version", "select", default="v5e", group="TPU (Tensor Processing Unit)",
               options=_opts(("v4", "v4"), ("v5e", "v5e"), ("v5p", "v5p")), required=False),
            _f("tpu_topology", "Configuration topology", "select", default="4", required=False,
               group="TPU (Tensor Processing Unit)",
               options=_opts(("1", "1x1 (1 chip)"), ("4", "2x2 (4 chips)"), ("16", "4x4 (16 chips)"),
                              ("32", "4x8 (32 chips)"), ("64", "8x8 (64 chips)"))),
            _f("tpu_hours_per_month", "Execution time (hours/month)", unit="TPU-hr", default=0,
               group="TPU (Tensor Processing Unit)",
               help_text="Hours the TPU topology runs per month; multiplied by chip count for total billable chip-hours."),
        ],
        pricing_dimensions=[
            _d("tpu-hours", "TPU chip-hours", "tpu_chip_hours_total_per_month", "TPU chip-hour", 1.2,
               rate_selector_field_id="tpu_type", rate_by_option={"v4": 3.22, "v5e": 1.2, "v5p": 4.2}),
        ],
    ),
    GCPServiceDefinition(
        service_id="vector-search",
        display_name="Vector Search",
        category=CAT_AI_ML,
        description="Managed approximate nearest-neighbor vector search.",
        icon="brain",
        configuration_schema=[
            _f("index_size_gb", "Index size (GB)", unit="GB", default=0, group="Index Storage & Queries"),
            _f("queries_per_month", "Queries/month", default=0, required=False, group="Index Storage & Queries"),
            _f("node_machine_type", "Node machine type", "select", default="e2-standard-2", required=False,
               group="Deployed Index Nodes",
               options=_opts(("e2-standard-2", "e2-standard-2"), ("e2-standard-4", "e2-standard-4"),
                              ("e2-standard-8", "e2-standard-8"), ("n2-standard-4", "n2-standard-4"))),
            _f("node_hours_per_month", "Node-hours/month", unit="node-hr", default=0, group="Deployed Index Nodes"),
            _f("index_updates_gb_per_month", "Index updates volume (GB/month)", unit="GB", default=0,
               required=False, group="Index Updates",
               help_text="Volume of batch or streaming vector embeddings inserted or updated."),
        ],
        pricing_dimensions=[
            _d("index", "Index storage", "index_size_gb", "GB/month", 3.5),
            _d("queries", "Queries", "queries_per_month", "million queries", 3.0, 1_000_000),
            _d("node-hours", "Deployed index node-hours", "node_hours_per_month", "node-hour", 0.07,
               rate_selector_field_id="node_machine_type",
               rate_by_option={"e2-standard-2": 0.07, "e2-standard-4": 0.14, "e2-standard-8": 0.28,
                                "n2-standard-4": 0.19}),
            _d("index-updates", "Index updates", "index_updates_gb_per_month", "GB", 0.06),
        ],
    ),

    # -- Security -----------------------------------------------------------
    GCPServiceDefinition(
        service_id="secret-manager",
        display_name="Secret Manager",
        category=CAT_SECURITY,
        description="Centralized secret storage and versioning.",
        icon="shield",
        configuration_schema=[
            _f("active_secrets", "Active secret versions", default=0, min_value=0),
            _f("access_operations_per_month", "Access operations/month", default=0, required=False),
        ],
        pricing_dimensions=[
            _d("secrets", "Active secrets", "active_secrets", "secret/month", 0.06),
            _d("access", "Access operations", "access_operations_per_month", "10,000 operations", 0.03, 10_000),
        ],
    ),
    GCPServiceDefinition(
        service_id="cloud-kms",
        display_name="Cloud KMS",
        category=CAT_SECURITY,
        description="Managed encryption key management.",
        icon="shield",
        configuration_schema=[
            _f("active_keys", "Active key versions", default=0, min_value=0),
            _f("operations_per_month", "Cryptographic operations/month", default=0, required=False),
        ],
        pricing_dimensions=[
            _d("keys", "Active keys", "active_keys", "key/month", 0.06),
            _d("operations", "Operations", "operations_per_month", "10,000 operations", 0.03, 10_000),
        ],
    ),
    GCPServiceDefinition(
        service_id="security-command-center",
        display_name="Security Command Center",
        category=CAT_SECURITY,
        description="Centralized security and risk management.",
        icon="shield",
        configuration_schema=[
            _f("tier", "Tier", "select", default="standard",
               options=_opts(("standard", "Standard (free)"), ("premium", "Premium")), required=False),
            _f("assets_monitored", "Monitored vCPUs / VMs (evaluation basis)", default=1, min_value=1,
               help_text="Security Command Center Premium evaluates cost from total compute usage "
                         "(vCPUs/VMs running) across the organization; Standard tier is free."),
        ],
        pricing_dimensions=[
            _d("assets", "Compute usage evaluated", "assets_monitored", "vCPU or VM/month", 0.50,
               rate_selector_field_id="tier", rate_by_option={"standard": 0.0, "premium": 0.50}),
        ],
    ),
    GCPServiceDefinition(
        service_id="certificate-manager",
        display_name="Certificate Manager",
        category=CAT_SECURITY,
        description="Managed TLS certificate provisioning.",
        icon="shield",
        configuration_schema=[_f("managed_certificates", "Managed certificates", default=1, min_value=1)],
        pricing_dimensions=[_d("certificates", "Certificates", "managed_certificates", "certificate/month", 0.75)],
    ),

    # -- Observability --------------------------------------------------
    GCPServiceDefinition(
        service_id="cloud-monitoring",
        display_name="Cloud Monitoring",
        category=CAT_OBSERVABILITY,
        description="Metrics, dashboards, and alerting.",
        icon="activity",
        configuration_schema=[
            _f("metrics_volume_mb_per_month", "Custom metrics ingestion volume (MB/month)", unit="MB", default=0,
               group="Custom Metrics Ingestion",
               help_text="Volume of non-GCP/custom metric data points ingested."),
            _f("api_calls_per_month", "Read/write API calls beyond free tier", default=0, required=False,
               group="API Calls"),
        ],
        pricing_dimensions=[
            _d("metrics", "Metrics volume", "metrics_volume_mb_per_month", "MB", 0.258),
            _d("api-calls", "API calls", "api_calls_per_month", "1,000 calls", 0.01, 1_000),
        ],
    ),
    GCPServiceDefinition(
        service_id="cloud-logging",
        display_name="Cloud Logging",
        category=CAT_OBSERVABILITY,
        description="Centralized log storage, search, and export.",
        icon="activity",
        # Priced by MessagingObservabilityPricingCalculator (ingestion volume
        # + documented 50 GiB/month free tier, plus extended-retention storage
        # below), not GenericServicePricingCalculator.
        configuration_schema=[
            _f("log_volume_gb_per_month", "Ingested log volume (GB/month)", unit="GB", default=0,
               group="Ingested Volume"),
            _f("retention_days", "Logging retention duration (days)", default=1, min_value=1, required=False,
               group="Storage Retention",
               help_text="Retention beyond the free 30-day default is priced from the GB/month field below."),
            _f("extended_retention_gb_per_month", "Retained storage beyond 30 days (GB/month)", unit="GB",
               default=0, required=False, group="Storage Retention",
               help_text="Log storage volume retained longer than the default 30-day free retention period."),
        ],
        pricing_dimensions=[],
    ),
    GCPServiceDefinition(
        service_id="cloud-trace",
        display_name="Cloud Trace",
        category=CAT_OBSERVABILITY,
        description="Distributed request tracing.",
        icon="activity",
        configuration_schema=[
            _f("spans_per_month", "Ingested span volume (millions/month)", default=0, required=False),
        ],
        pricing_dimensions=[_d("spans", "Spans", "spans_per_month", "million spans", 0.20, 1_000_000)],
    ),
    GCPServiceDefinition(
        service_id="error-reporting",
        display_name="Error Reporting",
        category=CAT_OBSERVABILITY,
        description="Real-time error aggregation and alerting.",
        icon="activity",
        configuration_schema=[
            _f("events_per_month", "Error events/month", default=0, required=False,
               help_text="Free of charge - included with Cloud Logging ingestion."),
        ],
        pricing_dimensions=[],
    ),
    GCPServiceDefinition(
        service_id="managed-prometheus",
        display_name="Managed Prometheus",
        category=CAT_OBSERVABILITY,
        description="Fully managed Prometheus-compatible metrics.",
        icon="activity",
        configuration_schema=[_f("samples_ingested_per_month_billion", "Samples ingested (billion/month)", unit="B samples", default=0)],
        pricing_dimensions=[_d("samples", "Samples ingested", "samples_ingested_per_month_billion", "billion samples", 60.0)],
    ),

    # -- DevOps -----------------------------------------------------------
    GCPServiceDefinition(
        service_id="cloud-build",
        display_name="Cloud Build",
        category=CAT_DEVOPS,
        description="Managed CI/CD build execution.",
        icon="git-branch",
        configuration_schema=[
            _f("machine_type", "Machine type", "select", default="default", required=False,
               group="Machine Type",
               options=_opts(("default", "Default (1 vCPU)"), ("high-cpu", "High-CPU (E2_HIGHCPU_8)"),
                              ("high-cpu-32", "High-CPU (E2_HIGHCPU_32)"))),
            _f("build_minutes_per_month", "Build minutes/month", unit="min", default=0, group="Build Duration"),
        ],
        pricing_dimensions=[
            _d("build-minutes", "Build minutes", "build_minutes_per_month", "minute", 0.003,
               rate_selector_field_id="machine_type",
               rate_by_option={"default": 0.003, "high-cpu": 0.016, "high-cpu-32": 0.064}),
        ],
    ),
    GCPServiceDefinition(
        service_id="artifact-registry",
        display_name="Artifact Registry",
        category=CAT_DEVOPS,
        description="Managed container/package artifact storage.",
        icon="git-branch",
        configuration_schema=[
            _f("storage_gb", "Storage volume (GB)", unit="GB", default=0, group="Storage Volume"),
            _f("network_egress_gb_per_month", "Network transfer / egress (GB/month)", unit="GB", default=0,
               required=False, group="Network Transfer",
               help_text="Data egress when pulling images outside GCP regions."),
        ],
        pricing_dimensions=[
            _d("storage", "Storage", "storage_gb", "GB/month", 0.10),
            _d("egress", "Network transfer", "network_egress_gb_per_month", "GB", 0.12),
        ],
    ),
    GCPServiceDefinition(
        service_id="cloud-deploy",
        display_name="Cloud Deploy",
        category=CAT_DEVOPS,
        description="Managed continuous delivery to GKE/Cloud Run/Compute Engine.",
        icon="git-branch",
        configuration_schema=[
            _f("active_delivery_pipelines", "Active delivery pipelines", default=1, min_value=1,
               group="Pipeline Targets"),
            _f("target_environments", "Target environments deployed to", default=1, min_value=1, required=False,
               group="Pipeline Targets"),
        ],
        pricing_dimensions=[
            _d("pipelines", "Delivery pipelines", "active_delivery_pipelines", "pipeline/month", 15.0),
            _d("targets", "Target environments", "target_environments", "target/month", 5.0),
        ],
    ),

    # -- API & Integration ------------------------------------------------
    GCPServiceDefinition(
        service_id="apigee",
        display_name="Apigee",
        category=CAT_INTEGRATION,
        description="Full lifecycle API management platform.",
        icon="plug",
        configuration_schema=[
            _f("commercial_model", "Commercial model", "select", default="pay_as_you_go", required=False,
               group="Commercial Model",
               options=_opts(("pay_as_you_go", "Pay-As-You-Go"), ("subscription_standard", "Subscription: Standard"),
                              ("subscription_enterprise", "Subscription: Enterprise"),
                              ("subscription_enterprise_plus", "Subscription: Enterprise Plus"))),
            _f("api_calls_per_month", "API proxy calls/month", default=0, group="API Proxy Calls"),
            _f("environment_node_hours_per_month", "Environment node-hours/month", unit="node-hr", default=0,
               required=False, group="Environment Size",
               help_text="Number of active environment nodes, provisioned per hour."),
        ],
        pricing_dimensions=[
            _d("api-calls", "API calls", "api_calls_per_month", "million calls", 15.0, 1_000_000,
               rate_selector_field_id="commercial_model",
               rate_by_option={"pay_as_you_go": 15.0, "subscription_standard": 10.0,
                                "subscription_enterprise": 7.0, "subscription_enterprise_plus": 5.0}),
            _d("environment", "Environment nodes", "environment_node_hours_per_month", "node-hour", 0.85),
        ],
    ),
    GCPServiceDefinition(
        service_id="api-gateway",
        display_name="API Gateway",
        category=CAT_INTEGRATION,
        description="Lightweight, fully managed API gateway.",
        icon="plug",
        configuration_schema=[
            _f("api_calls_per_month", "Call volume/month", default=0, group="Call Volume"),
            _f("bandwidth_egress_gb_per_month", "Bandwidth egress (GB/month)", unit="GB", default=0,
               required=False, group="Bandwidth Egress",
               help_text="Outbound data response payload size."),
        ],
        pricing_dimensions=[
            _d("api-calls", "API calls", "api_calls_per_month", "million calls", 3.0, 1_000_000),
            _d("egress", "Bandwidth egress", "bandwidth_egress_gb_per_month", "GB", 0.12),
        ],
    ),
]

SERVICE_CATALOG_BY_ID: dict[str, GCPServiceDefinition] = {s.service_id: s for s in GCP_SERVICE_CATALOG}
