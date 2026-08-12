"use client";

import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  BACKUP_FREQUENCIES,
  CLOUD_SQL_COMMITMENTS,
  CLOUD_SQL_ENGINES,
  CLOUD_SQL_MACHINE_TIERS,
  CLOUD_SQL_STORAGE_TYPES,
  DISK_TYPES,
  GPU_TYPES,
  MACHINE_FAMILIES,
  NORMALIZATION_STRATEGIES,
  OPERATING_SYSTEMS,
  PROVISIONING_MODELS,
  REGIONS,
} from "@/lib/types";
import type { AdditionalDiskRequirement, DiskType } from "@/lib/types";

const OS_LABELS: Record<string, string> = {
  linux: "Linux (free)",
  windows_server: "Windows Server",
  rhel: "Red Hat Enterprise Linux",
  suse: "SUSE Linux Enterprise Server",
};

const PROVISIONING_LABELS: Record<string, string> = {
  on_demand: "On-Demand",
  spot: "Spot (Preemptible)",
};
import type { WizardState } from "@/components/wizard/use-wizard-state";

function Field({ label, htmlFor, hint, children }: { label: string; htmlFor: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function ToggleSection({
  label,
  description,
  enabled,
  onChange,
  children,
}: {
  label: string;
  description: string;
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4">
      <label className="flex cursor-pointer items-start gap-3 rounded-md border border-border p-3 transition-colors hover:bg-muted/40">
        <Checkbox checked={enabled} onChange={(e) => onChange(e.target.checked)} className="mt-0.5" />
        <span>
          <span className="block text-sm font-medium">{label}</span>
          <span className="block text-xs text-muted-foreground">{description}</span>
        </span>
      </label>
      {enabled && <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">{children}</div>}
    </div>
  );
}

export function BasicsStep({ state }: { state: WizardState }) {
  const { requirement, update } = state;
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <Field label="Project name" htmlFor="project_name">
        <Input
          id="project_name"
          required
          value={requirement.project_name}
          onChange={(e) => update("project_name", e.target.value)}
          placeholder="e.g. Customer Portal Migration"
        />
      </Field>
      <Field label="Region" htmlFor="region">
        <Select id="region" value={requirement.region} onChange={(e) => update("region", e.target.value as typeof requirement.region)}>
          {REGIONS.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </Select>
      </Field>
      <Field
        label="Normalization strategy"
        htmlFor="strategy"
        hint="How unsupported values are adjusted to the nearest supported configuration."
      >
        <Select
          id="strategy"
          value={requirement.normalization_strategy ?? "balanced"}
          onChange={(e) => update("normalization_strategy", e.target.value as typeof requirement.normalization_strategy)}
        >
          {NORMALIZATION_STRATEGIES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Existing infrastructure notes (optional)" htmlFor="existing_notes">
        <Textarea
          id="existing_notes"
          value={requirement.existing_infrastructure_notes ?? ""}
          onChange={(e) => update("existing_infrastructure_notes", e.target.value || null)}
          placeholder="Anything already running that this estimate should account for..."
        />
      </Field>
    </div>
  );
}

export function SizingStep({ state }: { state: WizardState }) {
  const { requirement, update, sizingMode, setSizing } = state;
  return (
    <div className="flex flex-col gap-5">
      <div className="flex gap-3">
        <button
          type="button"
          onClick={() => setSizing("explicit")}
          className={cn(
            "flex-1 rounded-md border p-3 text-left text-sm transition-colors",
            sizingMode === "explicit" ? "border-primary bg-primary-50 dark:bg-primary-950" : "border-border hover:bg-muted/40",
          )}
        >
          <span className="block font-medium text-foreground">I know exactly what I need</span>
          <span className="block text-xs text-muted-foreground">Specify machine family, vCPU, RAM, and instance count directly.</span>
        </button>
        <button
          type="button"
          onClick={() => setSizing("business")}
          className={cn(
            "flex-1 rounded-md border p-3 text-left text-sm transition-colors",
            sizingMode === "business" ? "border-primary bg-primary-50 dark:bg-primary-950" : "border-border hover:bg-muted/40",
          )}
        >
          <span className="block font-medium text-foreground">Size it for me</span>
          <span className="block text-xs text-muted-foreground">Describe your users/traffic and let the AI recommendation engine choose.</span>
        </button>
      </div>

      {sizingMode === "explicit" && requirement.compute && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Machine family" htmlFor="machine_family">
            <Select
              id="machine_family"
              value={requirement.compute.machine_family}
              onChange={(e) => update("compute", { ...requirement.compute!, machine_family: e.target.value as typeof requirement.compute.machine_family })}
            >
              {MACHINE_FAMILIES.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Instance count" htmlFor="instance_count">
            <Input
              id="instance_count"
              type="number"
              min={1}
              value={requirement.compute.instance_count}
              onChange={(e) => update("compute", { ...requirement.compute!, instance_count: Number(e.target.value) })}
            />
          </Field>
          <Field label="vCPU (per instance)" htmlFor="vcpu">
            <Input
              id="vcpu"
              type="number"
              min={1}
              value={requirement.compute.vcpu}
              onChange={(e) => update("compute", { ...requirement.compute!, vcpu: Number(e.target.value) })}
            />
          </Field>
          <Field label="RAM GB (per instance)" htmlFor="ram_gb">
            <Input
              id="ram_gb"
              type="number"
              min={1}
              value={requirement.compute.ram_gb}
              onChange={(e) => update("compute", { ...requirement.compute!, ram_gb: Number(e.target.value) })}
            />
          </Field>
          <Field label="GPU type" htmlFor="gpu_type">
            <Select
              id="gpu_type"
              value={requirement.compute.gpu_type}
              onChange={(e) => update("compute", { ...requirement.compute!, gpu_type: e.target.value as typeof requirement.compute.gpu_type })}
            >
              {GPU_TYPES.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </Select>
          </Field>
          {requirement.compute.gpu_type !== "none" && (
            <Field label="GPU count (per instance)" htmlFor="gpu_count">
              <Input
                id="gpu_count"
                type="number"
                min={0}
                value={requirement.compute.gpu_count}
                onChange={(e) => update("compute", { ...requirement.compute!, gpu_count: Number(e.target.value) })}
              />
            </Field>
          )}
          <Field label="Provisioning model" htmlFor="provisioning_model" hint="Spot/Preemptible VMs are steeply discounted but can be reclaimed at any time.">
            <Select
              id="provisioning_model"
              value={requirement.compute.provisioning_model}
              onChange={(e) => update("compute", { ...requirement.compute!, provisioning_model: e.target.value as typeof requirement.compute.provisioning_model })}
            >
              {PROVISIONING_MODELS.map((p) => (
                <option key={p} value={p}>
                  {PROVISIONING_LABELS[p]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Operating system" htmlFor="operating_system" hint="Windows/RHEL/SUSE add a licensing surcharge on top of infrastructure cost.">
            <Select
              id="operating_system"
              value={requirement.compute.operating_system}
              onChange={(e) => update("compute", { ...requirement.compute!, operating_system: e.target.value as typeof requirement.compute.operating_system })}
            >
              {OPERATING_SYSTEMS.map((os) => (
                <option key={os} value={os}>
                  {OS_LABELS[os]}
                </option>
              ))}
            </Select>
          </Field>
          <div className="sm:col-span-2">
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={requirement.compute.hours_per_day === null && requirement.compute.days_per_month === null}
                onChange={(e) =>
                  update("compute", {
                    ...requirement.compute!,
                    hours_per_day: e.target.checked ? null : 24,
                    days_per_month: e.target.checked ? null : 30,
                  })
                }
              />
              Runs 24/7 (full billing month)
            </label>
          </div>
          {(requirement.compute.hours_per_day !== null || requirement.compute.days_per_month !== null) && (
            <>
              <Field label="Hours/day" htmlFor="hours_per_day" hint="e.g. 8 for a dev server that's shut down overnight.">
                <Input
                  id="hours_per_day"
                  type="number"
                  min={1}
                  max={24}
                  value={requirement.compute.hours_per_day ?? 24}
                  onChange={(e) => update("compute", { ...requirement.compute!, hours_per_day: Number(e.target.value) })}
                />
              </Field>
              <Field label="Days/month" htmlFor="days_per_month" hint="e.g. 22 for a dev server that's off on weekends.">
                <Input
                  id="days_per_month"
                  type="number"
                  min={1}
                  max={31}
                  value={requirement.compute.days_per_month ?? 30}
                  onChange={(e) => update("compute", { ...requirement.compute!, days_per_month: Number(e.target.value) })}
                />
              </Field>
            </>
          )}
        </div>
      )}

      {sizingMode === "business" && requirement.business && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Total users" htmlFor="total_users">
            <Input
              id="total_users"
              type="number"
              min={0}
              value={requirement.business.total_users ?? ""}
              onChange={(e) => update("business", { ...requirement.business!, total_users: e.target.value ? Number(e.target.value) : null })}
            />
          </Field>
          <Field label="Peak concurrent users" htmlFor="peak_concurrent_users">
            <Input
              id="peak_concurrent_users"
              type="number"
              min={0}
              value={requirement.business.peak_concurrent_users ?? ""}
              onChange={(e) => update("business", { ...requirement.business!, peak_concurrent_users: e.target.value ? Number(e.target.value) : null })}
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Notes (optional)" htmlFor="business_notes">
              <Textarea
                id="business_notes"
                value={requirement.business.notes ?? ""}
                onChange={(e) => update("business", { ...requirement.business!, notes: e.target.value || null })}
                placeholder="Anything else about the workload that should influence sizing..."
              />
            </Field>
          </div>
        </div>
      )}
    </div>
  );
}

export function StorageStep({ state }: { state: WizardState }) {
  const { requirement, update, toggleSection, defaults } = state;
  return (
    <ToggleSection
      label="Add block storage"
      description="Persistent disks attached to compute instances."
      enabled={!!requirement.storage}
      onChange={(enabled) => toggleSection("storage", enabled, defaults.storage)}
    >
      {requirement.storage && (
        <>
          <Field label="Disk type" htmlFor="disk_type">
            <Select
              id="disk_type"
              value={requirement.storage.disk_type}
              onChange={(e) => update("storage", { ...requirement.storage!, disk_type: e.target.value as typeof requirement.storage.disk_type })}
            >
              {DISK_TYPES.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Size (GB)" htmlFor="disk_size_gb">
            <Input
              id="disk_size_gb"
              type="number"
              min={1}
              value={requirement.storage.size_gb}
              onChange={(e) => update("storage", { ...requirement.storage!, size_gb: Number(e.target.value) })}
            />
          </Field>
          {requirement.storage.disk_type === "pd-extreme" && (
            <>
              <Field label="Provisioned IOPS" htmlFor="provisioned_iops">
                <Input
                  id="provisioned_iops"
                  type="number"
                  min={0}
                  value={requirement.storage.provisioned_iops}
                  onChange={(e) => update("storage", { ...requirement.storage!, provisioned_iops: Number(e.target.value) })}
                />
              </Field>
              <Field label="Provisioned throughput (MB/s)" htmlFor="provisioned_throughput_mbps">
                <Input
                  id="provisioned_throughput_mbps"
                  type="number"
                  min={0}
                  value={requirement.storage.provisioned_throughput_mbps}
                  onChange={(e) => update("storage", { ...requirement.storage!, provisioned_throughput_mbps: Number(e.target.value) })}
                />
              </Field>
            </>
          )}
          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={requirement.storage.snapshot_enabled}
              onChange={(e) => update("storage", { ...requirement.storage!, snapshot_enabled: e.target.checked })}
            />
            Enable snapshots
          </label>
          {requirement.storage.snapshot_enabled && (
            <>
              <Field label="Snapshot retention (days)" htmlFor="snapshot_retention_days">
                <Input
                  id="snapshot_retention_days"
                  type="number"
                  min={0}
                  value={requirement.storage.snapshot_retention_days}
                  onChange={(e) => update("storage", { ...requirement.storage!, snapshot_retention_days: Number(e.target.value) })}
                />
              </Field>
              <Field
                label="Backup/snapshot storage (GB/month)"
                htmlFor="snapshot_storage_gb"
                hint="If set, prices this directly instead of estimating from retention days."
              >
                <Input
                  id="snapshot_storage_gb"
                  type="number"
                  min={0}
                  value={requirement.storage.snapshot_storage_gb}
                  onChange={(e) => update("storage", { ...requirement.storage!, snapshot_storage_gb: Number(e.target.value) })}
                />
              </Field>
            </>
          )}
          <Field label="Local SSD blocks (per instance)" htmlFor="local_ssd_count" hint="Fixed-size 375 GB scratch disks, up to 24 per instance.">
            <Input
              id="local_ssd_count"
              type="number"
              min={0}
              max={24}
              value={requirement.storage.local_ssd_count}
              onChange={(e) => update("storage", { ...requirement.storage!, local_ssd_count: Number(e.target.value) })}
            />
          </Field>
          <div className="flex flex-col gap-2 sm:col-span-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="additional_disks">Additional disks (per instance)</Label>
              <button
                type="button"
                onClick={() =>
                  update("storage", {
                    ...requirement.storage!,
                    additional_disks: [...requirement.storage!.additional_disks, { disk_type: "pd-balanced", size_gb: 100 }],
                  })
                }
                className="text-xs font-medium text-primary hover:underline"
              >
                + Add disk
              </button>
            </div>
            {requirement.storage.additional_disks.length === 0 && (
              <p className="text-xs text-muted-foreground">No additional data disks.</p>
            )}
            {requirement.storage.additional_disks.map((disk: AdditionalDiskRequirement, i: number) => (
              <div key={i} className="flex items-center gap-2">
                <Select
                  aria-label={`Additional disk ${i + 1} type`}
                  value={disk.disk_type}
                  onChange={(e) => {
                    const next = [...requirement.storage!.additional_disks];
                    next[i] = { ...next[i], disk_type: e.target.value as DiskType };
                    update("storage", { ...requirement.storage!, additional_disks: next });
                  }}
                >
                  {DISK_TYPES.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </Select>
                <Input
                  aria-label={`Additional disk ${i + 1} size (GB)`}
                  type="number"
                  min={1}
                  value={disk.size_gb}
                  onChange={(e) => {
                    const next = [...requirement.storage!.additional_disks];
                    next[i] = { ...next[i], size_gb: Number(e.target.value) };
                    update("storage", { ...requirement.storage!, additional_disks: next });
                  }}
                />
                <button
                  type="button"
                  onClick={() => {
                    const next = requirement.storage!.additional_disks.filter((_, idx) => idx !== i);
                    update("storage", { ...requirement.storage!, additional_disks: next });
                  }}
                  className="text-xs font-medium text-destructive hover:underline"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </ToggleSection>
  );
}

export function DatabaseStep({ state }: { state: WizardState }) {
  const { requirement, update, toggleSection, defaults } = state;
  return (
    <ToggleSection
      label="Add a Cloud SQL database"
      description="Managed relational database (PostgreSQL, MySQL, or SQL Server)."
      enabled={!!requirement.database}
      onChange={(enabled) => toggleSection("database", enabled, defaults.database)}
    >
      {requirement.database && (
        <>
          <Field label="Engine" htmlFor="db_engine">
            <Select
              id="db_engine"
              value={requirement.database.engine}
              onChange={(e) => update("database", { ...requirement.database!, engine: e.target.value as typeof requirement.database.engine })}
            >
              {CLOUD_SQL_ENGINES.map((eng) => (
                <option key={eng} value={eng}>
                  {eng}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Compute size" htmlFor="db_machine_tier">
            <Select
              id="db_machine_tier"
              value={requirement.database.machine_tier}
              onChange={(e) => update("database", { ...requirement.database!, machine_tier: e.target.value as typeof requirement.database.machine_tier })}
            >
              {CLOUD_SQL_MACHINE_TIERS.map((t) => (
                <option key={t} value={t}>
                  {t === "shared-core" ? "Shared-core (db-f1-micro)" : "Custom (vCPU + RAM)"}
                </option>
              ))}
            </Select>
          </Field>
          {requirement.database.machine_tier === "custom" && (
            <>
              <Field label="vCPU" htmlFor="db_vcpu">
                <Input
                  id="db_vcpu"
                  type="number"
                  min={1}
                  value={requirement.database.vcpu}
                  onChange={(e) => update("database", { ...requirement.database!, vcpu: Number(e.target.value) })}
                />
              </Field>
              <Field label="RAM (GB)" htmlFor="db_ram_gb">
                <Input
                  id="db_ram_gb"
                  type="number"
                  min={1}
                  value={requirement.database.ram_gb}
                  onChange={(e) => update("database", { ...requirement.database!, ram_gb: Number(e.target.value) })}
                />
              </Field>
            </>
          )}
          <Field label="Storage type" htmlFor="db_storage_type">
            <Select
              id="db_storage_type"
              value={requirement.database.storage_type}
              onChange={(e) => update("database", { ...requirement.database!, storage_type: e.target.value as typeof requirement.database.storage_type })}
            >
              {CLOUD_SQL_STORAGE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.toUpperCase()}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Storage (GB)" htmlFor="db_size_gb">
            <Input
              id="db_size_gb"
              type="number"
              min={0}
              value={requirement.database.size_gb}
              onChange={(e) => update("database", { ...requirement.database!, size_gb: Number(e.target.value) })}
            />
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={requirement.database.high_availability}
              onChange={(e) => update("database", { ...requirement.database!, high_availability: e.target.checked })}
            />
            High availability (Regional, multi-zone failover)
          </label>
          <Field label="Retained backup storage (GB/month)" htmlFor="db_backup_storage_gb">
            <Input
              id="db_backup_storage_gb"
              type="number"
              min={0}
              value={requirement.database.backup_storage_gb}
              onChange={(e) => update("database", { ...requirement.database!, backup_storage_gb: Number(e.target.value) })}
            />
          </Field>
          <Field label="Binary log storage (GB/month)" htmlFor="db_binary_log_storage_gb">
            <Input
              id="db_binary_log_storage_gb"
              type="number"
              min={0}
              value={requirement.database.binary_log_storage_gb}
              onChange={(e) => update("database", { ...requirement.database!, binary_log_storage_gb: Number(e.target.value) })}
            />
          </Field>
          <Field label="Commitment" htmlFor="db_commitment">
            <Select
              id="db_commitment"
              value={requirement.database.commitment}
              onChange={(e) => update("database", { ...requirement.database!, commitment: e.target.value as typeof requirement.database.commitment })}
            >
              {CLOUD_SQL_COMMITMENTS.map((c) => (
                <option key={c} value={c}>
                  {c === "none" ? "None (on-demand)" : `${c} Committed Use Discount`}
                </option>
              ))}
            </Select>
          </Field>
        </>
      )}
    </ToggleSection>
  );
}

export function NetworkStep({ state }: { state: WizardState }) {
  const { requirement, update, toggleSection, defaults } = state;
  return (
    <ToggleSection
      label="Add networking"
      description="Load balancing, egress/ingress bandwidth, CDN, VPN."
      enabled={!!requirement.network}
      onChange={(enabled) => toggleSection("network", enabled, defaults.network)}
    >
      {requirement.network && (
        <>
          <Field label="Estimated egress (GB/month)" htmlFor="egress">
            <Input
              id="egress"
              type="number"
              min={0}
              value={requirement.network.estimated_egress_gb_per_month}
              onChange={(e) => update("network", { ...requirement.network!, estimated_egress_gb_per_month: Number(e.target.value) })}
            />
          </Field>
          <Field label="Estimated ingress (GB/month)" htmlFor="ingress">
            <Input
              id="ingress"
              type="number"
              min={0}
              value={requirement.network.estimated_ingress_gb_per_month}
              onChange={(e) => update("network", { ...requirement.network!, estimated_ingress_gb_per_month: Number(e.target.value) })}
            />
          </Field>
          <Field label="External IPs" htmlFor="external_ip_count">
            <Input
              id="external_ip_count"
              type="number"
              min={0}
              value={requirement.network.external_ip_count}
              onChange={(e) => update("network", { ...requirement.network!, external_ip_count: Number(e.target.value) })}
            />
          </Field>
          <div className="flex flex-col gap-2">
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={requirement.network.load_balancer_required}
                onChange={(e) => update("network", { ...requirement.network!, load_balancer_required: e.target.checked })}
              />
              Load balancer required
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={requirement.network.cdn_enabled}
                onChange={(e) => update("network", { ...requirement.network!, cdn_enabled: e.target.checked })}
              />
              CDN enabled
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={requirement.network.vpn_required}
                onChange={(e) => update("network", { ...requirement.network!, vpn_required: e.target.checked })}
              />
              VPN required
            </label>
          </div>
        </>
      )}
    </ToggleSection>
  );
}

export function KubernetesStep({ state }: { state: WizardState }) {
  const { requirement, update, toggleSection, defaults } = state;
  return (
    <ToggleSection
      label="Add Google Kubernetes Engine"
      description="Standard or Autopilot cluster."
      enabled={!!requirement.kubernetes}
      onChange={(enabled) => toggleSection("kubernetes", enabled, defaults.kubernetes)}
    >
      {requirement.kubernetes && (
        <>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={requirement.kubernetes.autopilot}
              onChange={(e) => update("kubernetes", { ...requirement.kubernetes!, autopilot: e.target.checked })}
            />
            Autopilot mode
          </label>
          {!requirement.kubernetes.autopilot && (
            <Field label="Node count" htmlFor="node_count">
              <Input
                id="node_count"
                type="number"
                min={0}
                value={requirement.kubernetes.node_count}
                onChange={(e) => update("kubernetes", { ...requirement.kubernetes!, node_count: Number(e.target.value) })}
              />
            </Field>
          )}
        </>
      )}
    </ToggleSection>
  );
}

export function AvailabilityStep({ state }: { state: WizardState }) {
  const { requirement, update, toggleSection, defaults } = state;
  return (
    <ToggleSection
      label="Add availability & backup requirements"
      description="High availability, uptime target, backups, disaster recovery."
      enabled={!!requirement.availability}
      onChange={(enabled) => toggleSection("availability", enabled, defaults.availability)}
    >
      {requirement.availability && (
        <>
          <Field label="Target uptime %" htmlFor="target_uptime_percent">
            <Input
              id="target_uptime_percent"
              type="number"
              min={0}
              max={100}
              step={0.01}
              value={requirement.availability.target_uptime_percent ?? ""}
              onChange={(e) =>
                update("availability", {
                  ...requirement.availability!,
                  target_uptime_percent: e.target.value ? Number(e.target.value) : null,
                })
              }
            />
          </Field>
          <Field label="Backup frequency" htmlFor="backup_frequency">
            <Select
              id="backup_frequency"
              value={requirement.availability.backup_frequency}
              onChange={(e) => update("availability", { ...requirement.availability!, backup_frequency: e.target.value as typeof requirement.availability.backup_frequency })}
            >
              {BACKUP_FREQUENCIES.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </Select>
          </Field>
          <div className="flex flex-col gap-2 sm:col-span-2">
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={requirement.availability.high_availability}
                onChange={(e) => update("availability", { ...requirement.availability!, high_availability: e.target.checked })}
              />
              High availability required
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={requirement.availability.disaster_recovery_required}
                onChange={(e) => update("availability", { ...requirement.availability!, disaster_recovery_required: e.target.checked })}
              />
              Disaster recovery required
            </label>
          </div>
        </>
      )}
    </ToggleSection>
  );
}
