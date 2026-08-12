// Human-readable reference for the 13 rules in the backend's validation
// engine (backend/app/validation/rules.py, ALL_RULES). Descriptions are
// transcribed from each rule's actual `evaluate()` logic and reason
// strings, not invented - if a rule's behavior changes, update this to
// match.

export interface RuleReferenceEntry {
  rule: string;
  fields: string[];
  category: string;
  description: string;
}

export const VALIDATION_RULES_REFERENCE: RuleReferenceEntry[] = [
  {
    rule: "cpu_validation",
    fields: ["compute.vcpu"],
    category: "Compute",
    description: "Checks the requested vCPU count exists as a standard configuration within the chosen machine family.",
  },
  {
    rule: "ram_validation",
    fields: ["compute.ram_gb"],
    category: "Compute",
    description: "Checks the requested RAM amount matches a supported machine type in the chosen machine family.",
  },
  {
    rule: "machine_family_validation",
    fields: ["compute.machine_family"],
    category: "Compute",
    description: "Checks the requested vCPU/RAM pair maps to an exact predefined machine type in the family.",
  },
  {
    rule: "gpu_validation",
    fields: ["compute.gpu_type", "compute.gpu_count"],
    category: "Compute",
    description: "Checks the GPU accelerator is recognized, compatible with the chosen machine family, and within the max-per-instance limit.",
  },
  {
    rule: "region_validation",
    fields: ["region"],
    category: "Location",
    description: "Checks the requested region exists in the active cloud provider's supported region catalog.",
  },
  {
    rule: "disk_validation",
    fields: ["storage.disk_type", "storage.size_gb"],
    category: "Storage",
    description: "Checks the disk type is recognized and the requested size falls within that disk type's min/max range.",
  },
  {
    rule: "cloud_storage_validation",
    fields: ["storage.snapshot_retention_days"],
    category: "Storage",
    description: "Flags snapshot retention beyond 365 days as unusual and cost-increasing when snapshots are enabled.",
  },
  {
    rule: "cloud_sql_tier_validation",
    fields: ["database.engine", "database.vcpu_ram"],
    category: "Database",
    description: "Checks the database engine has supported tiers, and that the requested vCPU/RAM pair matches an available Cloud SQL tier.",
  },
  {
    rule: "load_balancer_validation",
    fields: ["network.cdn_enabled", "network.external_ip_count"],
    category: "Network",
    description: "Checks CDN has a load balancer as its required origin, and that a load balancer has at least one external IP.",
  },
  {
    rule: "network_validation",
    fields: ["network.estimated_egress_gb_per_month"],
    category: "Network",
    description: "Flags very high monthly egress (>200,000 GB) as a case worth evaluating Interconnect or a committed network discount for.",
  },
  {
    rule: "kubernetes_validation",
    fields: ["kubernetes.autopilot", "kubernetes.node_count"],
    category: "Kubernetes",
    description: "Checks Autopilot availability and that the Standard-mode node count sits within the GKE-configured min/max range.",
  },
  {
    rule: "availability_validation",
    fields: ["availability.target_uptime_percent", "availability.high_availability"],
    category: "Availability",
    description: "Checks the target uptime doesn't exceed Google Cloud's highest published SLA (99.99%), and that high availability is enabled when the target requires it.",
  },
  {
    rule: "backup_validation",
    fields: ["availability.backup_frequency"],
    category: "Availability",
    description: "Checks that disaster recovery requirements are backed by an actual backup frequency, not left at 'none'.",
  },
];
