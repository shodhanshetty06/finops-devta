// TypeScript mirrors of backend/app/domain/*.py Pydantic schemas. Kept as a
// single hand-maintained file (no codegen) since the backend is the source
// of truth and schema changes are infrequent - see docs/ARCHITECTURE.md.

// -- Enums (backend/app/domain/enums.py) -------------------------------

export type Severity = "info" | "warning" | "blocker";

export const MACHINE_FAMILIES = ["e2", "n2", "n2d", "c2", "a2"] as const;
export type MachineFamily = (typeof MACHINE_FAMILIES)[number];

export const REGIONS = [
  "us-central1", "us-east1", "us-west1",
  "europe-west1", "europe-west4",
  "asia-south1", "asia-southeast1",
] as const;
export type RegionCode = (typeof REGIONS)[number];

export const DISK_TYPES = ["pd-standard", "pd-balanced", "pd-ssd", "pd-extreme"] as const;
export type DiskType = (typeof DISK_TYPES)[number];

export const GPU_TYPES = ["none", "nvidia-tesla-t4", "nvidia-l4", "nvidia-tesla-a100", "nvidia-tesla-v100"] as const;
export type GpuType = (typeof GPU_TYPES)[number];

export const PROVISIONING_MODELS = ["on_demand", "spot"] as const;
export type ProvisioningModel = (typeof PROVISIONING_MODELS)[number];

export const OPERATING_SYSTEMS = ["linux", "windows_server", "rhel", "suse"] as const;
export type OperatingSystem = (typeof OPERATING_SYSTEMS)[number];

export const CLOUD_SQL_ENGINES = ["postgres", "mysql", "sqlserver"] as const;
export type CloudSqlEngine = (typeof CLOUD_SQL_ENGINES)[number];

export const CLOUD_SQL_MACHINE_TIERS = ["shared-core", "custom"] as const;
export const CLOUD_SQL_STORAGE_TYPES = ["hdd", "ssd"] as const;
export const CLOUD_SQL_COMMITMENTS = ["none", "1-year", "3-year"] as const;

export const BACKUP_FREQUENCIES = ["none", "daily", "hourly"] as const;
export type BackupFrequency = (typeof BACKUP_FREQUENCIES)[number];

export const NORMALIZATION_STRATEGIES = ["conservative", "balanced", "performance"] as const;
export type NormalizationStrategy = (typeof NORMALIZATION_STRATEGIES)[number];

// -- Requirements (backend/app/domain/requirements.py) -----------------

export interface ComputeRequirement {
  machine_family: MachineFamily;
  vcpu: number;
  ram_gb: number;
  instance_count: number;
  gpu_type: GpuType;
  gpu_count: number;
  provisioning_model: ProvisioningModel;
  operating_system: OperatingSystem;
  hours_per_day: number | null;
  days_per_month: number | null;
}

export interface AdditionalDiskRequirement {
  disk_type: DiskType;
  size_gb: number;
}

export interface StorageRequirement {
  disk_type: DiskType;
  size_gb: number;
  snapshot_enabled: boolean;
  snapshot_retention_days: number;
  snapshot_storage_gb: number;
  provisioned_iops: number;
  provisioned_throughput_mbps: number;
  additional_disks: AdditionalDiskRequirement[];
  local_ssd_count: number;
}

export interface DatabaseRequirement {
  required: boolean;
  engine: CloudSqlEngine;
  machine_tier: "shared-core" | "custom";
  size_gb: number;
  storage_type: "hdd" | "ssd";
  vcpu: number;
  ram_gb: number;
  high_availability: boolean;
  backup_storage_gb: number;
  binary_log_storage_gb: number;
  commitment: "none" | "1-year" | "3-year";
}

export interface NetworkRequirement {
  load_balancer_required: boolean;
  external_ip_count: number;
  estimated_egress_gb_per_month: number;
  estimated_ingress_gb_per_month: number;
  cdn_enabled: boolean;
  vpn_required: boolean;
}

export interface KubernetesRequirement {
  required: boolean;
  autopilot: boolean;
  edition?: "standard" | "enterprise";
  regional?: boolean;
  provisioning_model?: "on_demand" | "spot";

  // Standard mode node pool - ignored by PricingEngine when autopilot=true.
  node_count: number;
  machine_family?: MachineFamily;
  node_vcpu?: number;
  node_ram_gb?: number;
  node_disk_type?: DiskType;
  node_disk_size_gb?: number;
  node_gpu_type?: GpuType;
  node_gpu_count?: number;

  // Autopilot mode - average concurrent pod resource requests.
  avg_pod_count?: number;
  pod_vcpu?: number;
  pod_memory_gb?: number;
  pod_ephemeral_storage_gb?: number;

  // Running duration for both modes - both unset means 24/7.
  hours_per_day?: number | null;
  days_per_month?: number | null;
}

export interface AvailabilityRequirement {
  high_availability: boolean;
  target_uptime_percent: number | null;
  backup_frequency: BackupFrequency;
  disaster_recovery_required: boolean;
}

export interface BusinessContext {
  total_users: number | null;
  peak_concurrent_users: number | null;
  notes: string | null;
}

// -- GCP service catalog (backend/app/catalog/service_catalog.py) -------
// A service's configuration form is rendered generically from
// `configuration_schema` - see components/service-catalog/dynamic-service-config-form.tsx.
// No frontend code should ever branch on a specific `service_id`.

export type ConfigFieldType = "number" | "select" | "boolean" | "text";

export interface ConfigFieldOption {
  value: string;
  label: string;
}

export interface ConfigFieldSchema {
  field_id: string;
  label: string;
  field_type: ConfigFieldType;
  unit: string | null;
  default: unknown;
  min_value: number | null;
  max_value: number | null;
  options: ConfigFieldOption[] | null;
  required: boolean;
  help_text: string | null;
  // Optional section label (e.g. "Scaling Constraints") - fields sharing a
  // group render together under a subheading; ungrouped fields render flat.
  group: string | null;
}

export interface PricingDimension {
  dimension_id: string;
  label: string;
  config_field_id: string;
  unit_label: string;
  unit_price_usd: number;
  quantity_divisor: number;
  // When set, the effective unit price is looked up from `rate_by_option`
  // using config[rate_selector_field_id] instead of unit_price_usd above.
  rate_selector_field_id: string | null;
  rate_by_option: Record<string, number> | null;
}

export type LegacyBinding = "storage" | "database" | "network" | "kubernetes";

export interface GCPServiceDefinition {
  service_id: string;
  display_name: string;
  category: string;
  description: string;
  icon: string;
  configuration_schema: ConfigFieldSchema[];
  pricing_dimensions: PricingDimension[];
  legacy_binding: LegacyBinding | null;
  active: boolean;
}

export interface ServiceSelection {
  service_id: string;
  config: Record<string, unknown>;
  quantity: number;
}

export interface CustomerRequirement {
  project_name: string;
  region: RegionCode;
  normalization_strategy: NormalizationStrategy | null;
  compute: ComputeRequirement | null;
  storage: StorageRequirement | null;
  database: DatabaseRequirement | null;
  network: NetworkRequirement | null;
  kubernetes: KubernetesRequirement | null;
  availability: AvailabilityRequirement | null;
  business: BusinessContext | null;
  selected_services: ServiceSelection[];
  existing_infrastructure_notes: string | null;
}

// -- Validation (backend/app/domain/validation.py) ----------------------

export interface ValidationResult {
  field: string;
  rule: string;
  requested_value: string;
  supported_value: string | null;
  is_valid: boolean;
  severity: Severity;
  reason: string;
  recommendation: string;
}

export interface ValidationReport {
  results: ValidationResult[];
}

// -- Assumptions ----------------------------------------------------------

export interface Assumption {
  field: string;
  requested_value: string;
  used_value: string;
  reason: string;
  strategy_applied: string | null;
}

// -- Architecture -----------------------------------------------------

export interface ArchitectureComponent {
  layer: string;
  service: string;
  rationale: string;
}

export interface ArchitectureRecommendation {
  summary: string;
  components: ArchitectureComponent[];
}

// -- Pricing (backend/app/domain/pricing.py) ---------------------------

export interface CostLineItem {
  category: string;
  description: string;
  sku_id: string | null;
  unit: string;
  quantity: number;
  unit_price: number;
  currency: string;
  monthly_amount: number;
  source: string;
}

export interface DiscountLineItem {
  name: string;
  description: string;
  percent_off: number;
  monthly_savings: number;
}

export type ResourceStatus = "valid" | "normalized" | "assumption" | "unsupported";

export interface ResourceCostSummary {
  resource_name: string;
  configuration: string;
  quantity: number;
  unit_cost: number;
  subtotal: number;
  currency: string;
  category: string | null;
  sku_id: string | null;
  pricing_source: string | null;
  region: string | null;
  requested_configuration: string | null;
  normalized_configuration: string | null;
  status: ResourceStatus;
  assumption_reason: string | null;
}

export interface CostBreakdown {
  currency: string;
  line_items: CostLineItem[];
  discounts: DiscountLineItem[];
  resource_summaries: ResourceCostSummary[];
  category_totals: Record<string, number>;
  subtotal_monthly: number;
  discount_total_monthly: number;
  tax_rate_percent: number;
  tax_monthly: number;
  support_plan_percent: number;
  support_monthly: number;
  total_monthly: number;
  total_yearly: number;
  total_three_year: number;
}

// -- Estimate (backend/app/domain/estimate.py) --------------------------

export interface NormalizedDisk {
  disk_type: string;
  size_gb: number;
}

export interface NormalizedSpec {
  region: string;
  machine_type: string | null;
  vcpu: number | null;
  ram_gb: number | null;
  instance_count: number | null;
  provisioning_model: string | null;
  operating_system: string | null;
  running_hours_per_month: number | null;
  disk_type: string | null;
  disk_size_gb: number | null;
  additional_disks: NormalizedDisk[];
  local_ssd_count: number;
  gpu_type: string | null;
  gpu_count: number;
  database_tier: string | null;
  database_size_gb: number | null;
  kubernetes_node_count: number | null;
  load_balancer: boolean;
  static_ip_count: number;
}

export interface AuditLogEntry {
  timestamp: string;
  actor: string;
  action: string;
  details: string;
}

export interface AuditLog {
  entries: AuditLogEntry[];
}

export interface EstimateResult {
  estimate_id: string;
  project_name: string;
  strategy_used: string;
  original_request: CustomerRequirement;
  normalized_spec: NormalizedSpec;
  assumptions: Assumption[];
  validation: ValidationReport;
  architecture: ArchitectureRecommendation;
  cost: CostBreakdown;
  audit_log: AuditLog;
}

// -- Auth (backend/app/domain/auth.py) -----------------------------------

export type UserRole = "admin" | "consultant" | "customer";

export interface UserRead {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

// -- Projects (backend/app/domain/project.py) ----------------------------

export interface ProjectRead {
  id: number;
  name: string;
  owner_id: number;
  created_at: string;
  updated_at: string;
  latest_version: number | null;
}

export interface EstimateVersionSummary {
  version: number;
  estimate_id: string;
  created_at: string;
  created_by_id: number;
  total_monthly: number;
  currency: string;
}

export interface EstimateVersionDetail extends EstimateVersionSummary {
  request: CustomerRequirement;
  result: EstimateResult;
}

// -- Optimization (backend/app/domain/optimization.py) --------------------

export interface UsageMetrics {
  avg_cpu_utilization_percent: number;
  peak_cpu_utilization_percent: number;
  avg_ram_utilization_percent?: number | null;
  observation_period_days?: number;
}

export type RightsizingAction = "downsize" | "upsize" | "terminate_idle" | "no_change";

export interface RightsizingFinding {
  resource_description: string;
  action: RightsizingAction;
  reason: string;
  current_machine_type: string;
  current_monthly_cost: number;
  recommended_machine_type: string | null;
  recommended_monthly_cost: number | null;
  monthly_savings: number;
  currency: string;
}

export interface RightsizingReport {
  findings: RightsizingFinding[];
  total_monthly_savings: number;
  currency: string;
}

export type WorkloadStability = "steady" | "variable";

export interface CommitmentTermOption {
  term_years: number;
  discount_percent: number;
  monthly_cost_with_commitment: number;
  monthly_savings_vs_on_demand: number;
  annual_savings_vs_on_demand: number;
}

export interface CommitmentRecommendation {
  on_demand_discountable_monthly_cost: number;
  options: CommitmentTermOption[];
  recommended_term_years: number;
  recommendation_reason: string;
  currency: string;
}

export interface CostForecastPoint {
  month_index: number;
  projected_monthly_cost: number;
  cumulative_cost: number;
}

export interface CostForecast {
  starting_monthly_cost: number;
  monthly_growth_percent: number;
  months: number;
  points: CostForecastPoint[];
  total_projected_cost: number;
  currency: string;
  methodology_note: string;
}

export interface CarbonEstimate {
  region: string;
  estimated_vcpu_hours_per_month: number;
  grid_carbon_intensity_gco2e_per_kwh: number;
  estimated_kwh_per_month: number;
  estimated_kgco2e_per_month: number;
  methodology_note: string;
}

export interface RegionCostOption {
  region: string;
  total_monthly: number;
  currency: string;
}

export interface RegionComparison {
  options: RegionCostOption[];
  cheapest_region: string;
  most_expensive_region: string;
  max_savings_monthly: number;
  currency: string;
}

export interface ScenarioRequest {
  name: string;
  overrides: Record<string, unknown>;
}

export interface ScenarioOutcome {
  name: string;
  total_monthly: number;
  total_yearly: number;
  currency: string;
  delta_vs_base_monthly: number;
  delta_vs_base_percent: number;
}

export interface ScenarioComparison {
  base: ScenarioOutcome;
  scenarios: ScenarioOutcome[];
}

export interface CloudCostOption {
  cloud_provider: string;
  total_monthly: number;
  currency: string;
  primary_machine_type: string | null;
}

export interface CloudComparison {
  options: CloudCostOption[];
  cheapest_cloud: string;
  most_expensive_cloud: string;
  max_savings_monthly: number;
  currency: string;
}

export interface VersionComparison {
  from_version: number;
  to_version: number;
  from_total_monthly: number;
  to_total_monthly: number;
  delta_monthly: number;
  delta_percent: number;
  currency: string;
  category_deltas: Record<string, number>;
}

// -- Intake (backend/app/domain/intake.py) -------------------------------

export interface ParseIssue {
  field: string;
  message: string;
  severity: Severity;
}

export interface IntakeResponse {
  requirement: CustomerRequirement | null;
  issues: ParseIssue[];
  notes: Assumption[];
  estimate: EstimateResult | null;
}

// -- Catalog (backend/app/catalog/models.py) -----------------------------

export interface MachineTypeSpec {
  name: string;
  family: string;
  vcpu: number;
  ram_gb: number;
  supports_gpu: boolean;
}

export interface DiskTypeSpec {
  name: string;
  min_size_gb: number;
  max_size_gb: number;
  description: string;
}

export interface GpuSpec {
  name: string;
  max_per_instance: number;
  compatible_families: string[];
}

export interface RegionSpec {
  code: string;
  display_name: string;
  multi_zone: boolean;
}

export interface CloudSqlTierSpec {
  tier: string;
  vcpu: number;
  ram_gb: number;
  engines: string[];
}

export interface GkeConfig {
  autopilot_available: boolean;
  standard_available: boolean;
  min_node_count: number;
  max_node_count: number;
}

// -- API error shape (backend/app/main.py exception handlers) -----------

export interface ApiErrorBody {
  error: string;
  message: string;
  results?: ValidationResult[];
}

// -- Display-currency conversion (backend/app/domain/currency.py) -------
// Purely presentational - never changes how an estimate was actually
// priced (that stays in EstimateResult.cost.currency, always USD today).

export interface ExchangeRatesResponse {
  base: string;
  rates: Record<string, number>;
  as_of: string;
  source: string;
  fetched_at: string;
  stale: boolean;
  supported_currencies: string[];
}
