"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { useMemo } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { catalogApi } from "@/lib/api-client";
import { FAMILY_CATEGORIES, FAMILY_INFO, familyLabel } from "@/lib/machine-family-info";
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
import type { AdditionalDiskRequirement, DiskType, MachineFamilyCapability } from "@/lib/types";

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

/** Client-side mirror of the vCPU/RAM range checks
 * `CustomMachineTypeValidationRule` runs authoritatively on the backend
 * (see backend/app/validation/rules.py) - gives immediate feedback while
 * typing instead of waiting for the debounced /validate round-trip. The
 * backend result (via ValidationPanel) remains the source of truth. */
function customShapeIssue(vcpu: number, ramGb: number, cap: MachineFamilyCapability): string | null {
  if (cap.min_vcpu != null && vcpu < cap.min_vcpu) return `vCPU must be at least ${cap.min_vcpu} for this family.`;
  if (cap.max_vcpu != null && vcpu > cap.max_vcpu) return `vCPU must be at most ${cap.max_vcpu} for this family.`;
  if (cap.vcpu_step > 1 && vcpu !== 1 && vcpu % cap.vcpu_step !== 0) return `vCPU must be a multiple of ${cap.vcpu_step} (or exactly 1).`;
  const ratio = vcpu > 0 ? ramGb / vcpu : 0;
  if (cap.min_ram_gb_per_vcpu != null && ratio < cap.min_ram_gb_per_vcpu - 1e-9) {
    return `RAM is too low for ${vcpu} vCPU - at least ${(cap.min_ram_gb_per_vcpu * vcpu).toFixed(1)} GB needed.`;
  }
  if (cap.max_ram_gb_per_vcpu != null && ratio > cap.max_ram_gb_per_vcpu + 1e-9) {
    return `RAM is too high for ${vcpu} vCPU - at most ${(cap.max_ram_gb_per_vcpu * vcpu).toFixed(1)} GB allowed.`;
  }
  return null;
}

function customRangeHint(cap: MachineFamilyCapability): string {
  const parts: string[] = [];
  if (cap.min_vcpu != null || cap.max_vcpu != null) {
    parts.push(`${cap.min_vcpu ?? 1}-${cap.max_vcpu ?? "∞"} vCPU${cap.vcpu_step > 1 ? ` (step of ${cap.vcpu_step})` : ""}`);
  }
  if (cap.min_ram_gb_per_vcpu != null || cap.max_ram_gb_per_vcpu != null) {
    parts.push(`${cap.min_ram_gb_per_vcpu ?? 0}-${cap.max_ram_gb_per_vcpu ?? "∞"} GB RAM per vCPU`);
  }
  return parts.join(" · ");
}

function Field({ label, htmlFor, hint, children }: { label: string; htmlFor: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

/** Number input with a unit suffix ("vCPU", "GB") inside the field, plus an
 * optional inline error - decorative only, never part of the accessible
 * label text (see the e2e specs' getByLabel("vCPU (per instance)") etc.). */
function UnitInput({
  id,
  unit,
  value,
  onChange,
  min = 1,
  error,
}: {
  id: string;
  unit: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  error?: string | null;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="relative">
        <Input
          id={id}
          type="number"
          min={min}
          value={value}
          aria-invalid={!!error}
          aria-describedby={error ? `${id}-error` : undefined}
          onChange={(e) => onChange(Number(e.target.value))}
          className={cn("pr-14", error && "border-error-400 focus-visible:ring-error-400")}
        />
        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">{unit}</span>
      </div>
      {error && (
        <p id={`${id}-error`} role="alert" className="flex items-center gap-1 text-xs text-error-600 dark:text-error-400">
          <AlertTriangle className="h-3 w-3 shrink-0" />
          {error}
        </p>
      )}
    </div>
  );
}

function ComputeConfigSummary({
  compute,
  region,
  selectedMachineType,
  regionAvailable,
  shapeIssue,
}: {
  compute: NonNullable<WizardState["requirement"]["compute"]>;
  region: string;
  selectedMachineType: { name: string; vcpu: number; ram_gb: number } | undefined;
  regionAvailable: boolean;
  shapeIssue?: string | null;
}) {
  const willPrice = regionAvailable && !shapeIssue;
  const isCustom = compute.machine_type_kind === "custom" && compute.machine_type == null;
  const isPredefined = compute.machine_type != null && !!selectedMachineType;
  const familyText = familyLabel(compute.machine_family);

  let title: string;
  let sizeLine: string;
  if (isPredefined && selectedMachineType) {
    title = `${familyText} · Predefined`;
    sizeLine = `${selectedMachineType.name} — ${selectedMachineType.vcpu} vCPU · ${selectedMachineType.ram_gb} GiB RAM`;
  } else if (isCustom) {
    title = `${familyText} · Custom`;
    sizeLine = `${compute.vcpu} vCPU · ${compute.ram_gb} GB RAM`;
  } else {
    title = `${familyText} · Auto-sized`;
    sizeLine = `~${compute.vcpu} vCPU · ${compute.ram_gb} GB RAM requested — nearest predefined size will be used`;
  }
  if (compute.instance_count > 1) sizeLine += ` × ${compute.instance_count} instances`;

  return (
    <div
      key={`${title}-${sizeLine}`}
      className="flex flex-col gap-1 rounded-lg border border-border bg-muted/40 px-4 py-3 text-sm animate-fade-in motion-reduce:animate-none"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium text-foreground">{title}</span>
        {willPrice ? (
          <Badge variant="success" className="gap-1"><CheckCircle2 className="h-3 w-3" />Will price as configured</Badge>
        ) : (
          <Badge variant="destructive" className="gap-1">
            <AlertTriangle className="h-3 w-3" />
            {regionAvailable ? "Fix vCPU/RAM to continue" : "Blocked in this region"}
          </Badge>
        )}
      </div>
      <p className="text-muted-foreground">{sizeLine}</p>
      <p className="text-muted-foreground">Region: {region}</p>
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
      <Field
        label="Project name (optional)"
        htmlFor="project_name"
        hint="Leave blank for a quick, unnamed estimate - a placeholder name is used until you save this to a project."
      >
        <Input
          id="project_name"
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
  const compute = requirement.compute;

  // Both queries are small, mostly-static catalogs (16 families, <=24 types
  // per family) - fetched once and cached, so the custom-support/region
  // indicators below never wait on the debounced /validate call the way the
  // full ValidationPanel does (Phase 8 requirement: instant feedback).
  const familyCapabilitiesQuery = useQuery({
    queryKey: ["catalog-machine-family-capabilities"],
    queryFn: catalogApi.machineFamilyCapabilities,
    staleTime: Infinity,
  });
  const capabilitiesByFamily = useMemo(() => {
    const map = new Map<string, MachineFamilyCapability>();
    for (const c of familyCapabilitiesQuery.data ?? []) map.set(c.family, c);
    return map;
  }, [familyCapabilitiesQuery.data]);
  const capability = compute ? capabilitiesByFamily.get(compute.machine_family) : undefined;
  const regionAvailable = !capability?.available_regions || capability.available_regions.includes(requirement.region);

  const machineTypesQuery = useQuery({
    queryKey: ["catalog-machine-types", compute?.machine_family],
    queryFn: () => catalogApi.machineTypes(compute!.machine_family),
    enabled: !!compute && compute.machine_type != null,
    staleTime: 60_000,
  });
  const machineTypeOptions: ComboboxOption[] = useMemo(
    () =>
      (machineTypesQuery.data ?? []).map((m) => ({
        value: m.name,
        label: m.name,
        sublabel: `${m.vcpu} vCPU · ${m.ram_gb} GiB RAM`,
      })),
    [machineTypesQuery.data],
  );
  const selectedMachineType = machineTypesQuery.data?.find((m) => m.name === compute?.machine_type);
  const customIssue = compute && compute.machine_type_kind === "custom" && capability?.supports_custom
    ? customShapeIssue(compute.vcpu, compute.ram_gb, capability)
    : null;

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
        <button
          type="button"
          onClick={() => setSizing("none")}
          className={cn(
            "flex-1 rounded-md border p-3 text-left text-sm transition-colors",
            sizingMode === "none" ? "border-primary bg-primary-50 dark:bg-primary-950" : "border-border hover:bg-muted/40",
          )}
        >
          <span className="block font-medium text-foreground">None</span>
          <span className="block text-xs text-muted-foreground">No Compute Engine VM in this estimate - price other GCP services only.</span>
        </button>
      </div>

      {sizingMode === "none" && (
        <p className="text-xs text-muted-foreground">
          No VM will be included in the cost calculation. Add other GCP services below to price the rest of the workload.
        </p>
      )}

      {sizingMode === "explicit" && requirement.compute && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Machine family" htmlFor="machine_family" hint={FAMILY_INFO[requirement.compute.machine_family].description}>
            <Select
              id="machine_family"
              value={requirement.compute.machine_family}
              onChange={(e) => {
                const nextFamily = e.target.value as typeof requirement.compute.machine_family;
                const c = requirement.compute!;
                update("compute", {
                  ...c,
                  machine_family: nextFamily,
                  // A predefined type name or custom shape is specific to the
                  // previous family - clearing it here avoids silently
                  // pricing e.g. "n4-standard-4" while displaying "N2D".
                  machine_type: c.machine_type != null ? "" : c.machine_type,
                });
              }}
            >
              {FAMILY_CATEGORIES.map((category) => {
                const families = MACHINE_FAMILIES.filter((f) => FAMILY_INFO[f].category === category);
                if (families.length === 0) return null;
                return (
                  <optgroup key={category} label={category}>
                    {families.map((f) => (
                      <option key={f} value={f}>
                        {familyLabel(f)} - {FAMILY_INFO[f].short}
                      </option>
                    ))}
                  </optgroup>
                );
              })}
            </Select>
          </Field>
          <Field label="Machine type" htmlFor="machine_config_mode" hint="Predefined types resolve their own vCPU/RAM automatically. Custom prices the exact vCPU/RAM below.">
            <Select
              id="machine_config_mode"
              value={requirement.compute.machine_type ? "predefined_name" : requirement.compute.machine_type_kind === "custom" ? "custom" : "auto"}
              onChange={(e) => {
                const mode = e.target.value;
                const c = requirement.compute!;
                if (mode === "predefined_name") {
                  update("compute", { ...c, machine_type: c.machine_type || "", machine_type_kind: null });
                } else if (mode === "custom") {
                  update("compute", { ...c, machine_type: null, machine_type_kind: "custom" });
                } else {
                  update("compute", { ...c, machine_type: null, machine_type_kind: null });
                }
              }}
            >
              <option value="auto">Auto (nearest predefined size)</option>
              <option value="predefined_name">Predefined type</option>
              <option value="custom" disabled={capability != null && !capability.supports_custom}>
                Custom vCPU / RAM{capability != null && !capability.supports_custom ? " (not supported)" : ""}
              </option>
            </Select>
          </Field>

          <div className="sm:col-span-2">
            {capability == null ? null : capability.supports_custom ? (
              <Badge variant="success" className="gap-1.5">
                <CheckCircle2 className="h-3 w-3" />
                Custom configuration supported for {familyLabel(requirement.compute.machine_family)}
              </Badge>
            ) : (
              <Badge variant="secondary" className="gap-1.5">
                Custom configuration not supported for {familyLabel(requirement.compute.machine_family)} - fixed predefined sizes only
              </Badge>
            )}
          </div>

          {!regionAvailable && capability?.available_regions && (
            <div className="sm:col-span-2">
              <Alert variant="warning" title={`${familyLabel(requirement.compute.machine_family)} is not available in ${requirement.region}`}>
                This family currently launches only in: {capability.available_regions.join(", ")}. Calculating an estimate with
                this combination will be blocked - choose a different region or machine family.
              </Alert>
            </div>
          )}

          {requirement.compute.machine_type != null && (
            <div className="sm:col-span-2">
              <Field
                label="Predefined machine type"
                htmlFor="machine_type"
                hint={selectedMachineType ? `${selectedMachineType.vcpu} vCPU · ${selectedMachineType.ram_gb} GiB RAM` : "Search by name, e.g. \"standard-4\" or \"highmem\"."}
              >
                <Combobox
                  id="machine_type"
                  ariaLabel="Predefined machine type"
                  value={requirement.compute.machine_type}
                  options={machineTypeOptions}
                  disabled={machineTypesQuery.isLoading}
                  placeholder={machineTypesQuery.isLoading ? "Loading machine types..." : "Search machine types..."}
                  emptyText={`No ${familyLabel(requirement.compute.machine_family)} machine types match.`}
                  onChange={(value) => update("compute", { ...requirement.compute!, machine_type: value })}
                />
              </Field>
            </div>
          )}
          <Field label="Instance count" htmlFor="instance_count">
            <Input
              id="instance_count"
              type="number"
              min={1}
              value={requirement.compute.instance_count}
              onChange={(e) => update("compute", { ...requirement.compute!, instance_count: Number(e.target.value) })}
            />
          </Field>
          {requirement.compute.machine_type == null && (
            <>
              <Field label={requirement.compute.machine_type_kind === "custom" ? "vCPU (custom, exact)" : "vCPU (per instance)"} htmlFor="vcpu">
                <UnitInput
                  id="vcpu"
                  unit="vCPU"
                  value={requirement.compute.vcpu}
                  onChange={(vcpu) => update("compute", { ...requirement.compute!, vcpu })}
                  error={customIssue}
                />
              </Field>
              <Field label={requirement.compute.machine_type_kind === "custom" ? "RAM GB (custom, exact)" : "RAM GB (per instance)"} htmlFor="ram_gb"
                hint={requirement.compute.machine_type_kind === "custom" && capability?.supports_custom ? customRangeHint(capability) : undefined}
              >
                <UnitInput
                  id="ram_gb"
                  unit="GB"
                  value={requirement.compute.ram_gb}
                  onChange={(ram_gb) => update("compute", { ...requirement.compute!, ram_gb })}
                  error={customIssue}
                />
              </Field>
            </>
          )}

          <div className="sm:col-span-2">
            <ComputeConfigSummary
              compute={requirement.compute}
              region={requirement.region}
              selectedMachineType={selectedMachineType}
              regionAvailable={regionAvailable}
              shapeIssue={customIssue}
            />
          </div>

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
