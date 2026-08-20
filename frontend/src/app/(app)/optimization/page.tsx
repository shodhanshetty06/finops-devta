"use client";

// Resource Optimization: pick an existing saved estimate's catalog resources
// and compare their current configuration/cost against a proposed
// upgrade/downgrade. This page invents no pricing of its own - every dollar
// figure comes from POST /api/v1/optimization/compare-scenarios (see
// app/optimization/comparison_engine.py::ScenarioComparisonEngine), which
// re-runs the *same* validation/normalization/pricing pipeline as every
// other estimate on this platform. A resource's own cost (and the cost of
// its proposed replacement) is isolated by diffing two real, fully-priced
// requirements - one with the resource removed, one with it swapped in -
// never by re-deriving a unit price ourselves.
import { Suspense, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowDownCircle, ArrowUpCircle, FolderSearch, Layers, Scale } from "lucide-react";
import { toast } from "sonner";

import { DynamicServiceConfigForm } from "@/components/service-catalog/dynamic-service-config-form";
import { serviceIcon } from "@/components/service-catalog/service-icons";
import { Badge } from "@/components/ui/badge";
import { buttonVariants, Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/finops/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ValidationPanel } from "@/components/validation-panel";
import { useCurrency } from "@/contexts/currency-context";
import { apiErrorMessage, catalogApi, estimateApi, optimizationApi, projectsApi } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type {
  CustomerRequirement,
  EstimateVersionDetail,
  GCPServiceDefinition,
  ScenarioRequest,
  ServiceSelection,
  ValidationReport,
} from "@/lib/types";

// -- Grouping existing selections into "resources" -------------------------
// Selections that share the same service_id AND the same config are the
// same resource just added more than once (identical to how
// app/catalog/resource_summary.py::build_resource_summaries groups the
// server-side cost view) - grouped so the picker shows one row per distinct
// resource/configuration instead of one row per raw selection.

interface ResourceGroup {
  key: string;
  service_id: string;
  definition: GCPServiceDefinition | undefined;
  originalConfig: Record<string, unknown>;
  originalQuantity: number;
  memberIndices: number[];
}

interface Proposal {
  config: Record<string, unknown>;
  quantity: number;
}

function stableConfigKey(config: Record<string, unknown>): string {
  return JSON.stringify(Object.keys(config).sort().map((k) => [k, config[k]]));
}

function describeConfig(definition: GCPServiceDefinition | undefined, config: Record<string, unknown>): string {
  const entries = Object.entries(config);
  if (entries.length === 0) return "Default configuration";
  const schemaById = new Map((definition?.configuration_schema ?? []).map((f) => [f.field_id, f]));
  return entries
    .map(([fieldId, value]) => {
      const field = schemaById.get(fieldId);
      const label = field?.label ?? fieldId;
      const unit = field?.unit ? ` ${field.unit}` : "";
      return `${label}: ${String(value)}${unit}`;
    })
    .join(", ");
}

function buildGroups(selections: ServiceSelection[], definitionsById: Map<string, GCPServiceDefinition>): ResourceGroup[] {
  const groups = new Map<string, ResourceGroup>();
  const order: string[] = [];
  selections.forEach((selection, idx) => {
    const key = `${selection.service_id}::${stableConfigKey(selection.config)}`;
    let group = groups.get(key);
    if (!group) {
      group = {
        key,
        service_id: selection.service_id,
        definition: definitionsById.get(selection.service_id),
        originalConfig: selection.config,
        originalQuantity: 0,
        memberIndices: [],
      };
      groups.set(key, group);
      order.push(key);
    }
    group.originalQuantity += Math.max(selection.quantity, 1);
    group.memberIndices.push(idx);
  });
  return order.map((k) => groups.get(k) as ResourceGroup);
}

function withoutGroup(selections: ServiceSelection[], group: ResourceGroup): ServiceSelection[] {
  return selections.filter((_, idx) => !group.memberIndices.includes(idx));
}

function withProposedGroup(selections: ServiceSelection[], group: ResourceGroup, proposal: Proposal): ServiceSelection[] {
  return [...withoutGroup(selections, group), { service_id: group.service_id, config: proposal.config, quantity: proposal.quantity }];
}

function combinedProposedSelections(
  selections: ServiceSelection[],
  groups: ResourceGroup[],
  selectedKeys: Set<string>,
  proposals: Record<string, Proposal>,
): ServiceSelection[] {
  const removeIndices = new Set<number>();
  groups.forEach((g) => {
    if (selectedKeys.has(g.key)) g.memberIndices.forEach((i) => removeIndices.add(i));
  });
  const base = selections.filter((_, idx) => !removeIndices.has(idx));
  const additions = groups
    .filter((g) => selectedKeys.has(g.key))
    .map((g) => {
      const p = proposals[g.key];
      return { service_id: g.service_id, config: p.config, quantity: p.quantity };
    });
  return [...base, ...additions];
}

const round2 = (n: number) => Math.round(n * 100) / 100;

// -- Comparison result -------------------------------------------------

interface ResourceComparisonRow {
  key: string;
  displayName: string;
  currentConfigText: string;
  proposedConfigText: string;
  currentQuantity: number;
  proposedQuantity: number;
  currentMonthly: number;
  proposedMonthly: number;
  monthlyDiff: number;
  annualDiff: number;
  percentChange: number;
  intent: "upgrade" | "downgrade";
  currency: string;
}

interface ComparisonResult {
  currency: string;
  rows: ResourceComparisonRow[];
  currentTotal: number;
  proposedTotal: number;
  totalMonthlyDiff: number;
  totalAnnualDiff: number;
  totalPercentChange: number;
}

function ImpactBadge({ amount }: { amount: number }) {
  if (amount < 0) return <Badge variant="success">Savings</Badge>;
  if (amount > 0) return <Badge variant="warning">Additional cost</Badge>;
  return <Badge variant="secondary">No change</Badge>;
}

function ComparisonResultsView({ result }: { result: ComparisonResult }) {
  const { formatMoney } = useCurrency();

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Scale className="size-4" />
            Overall: current total vs. proposed total
          </CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="flex flex-col gap-1">
            <p className="text-xs text-muted-foreground">Current total</p>
            <p className="text-lg font-semibold text-foreground">{formatMoney(result.currentTotal, result.currency)}/mo</p>
          </div>
          <div className="flex flex-col gap-1">
            <p className="text-xs text-muted-foreground">Proposed total</p>
            <p className="text-lg font-semibold text-foreground">{formatMoney(result.proposedTotal, result.currency)}/mo</p>
          </div>
          <div className="flex flex-col gap-1">
            <p className="text-xs text-muted-foreground">Monthly difference</p>
            <p className={cn("text-lg font-semibold", result.totalMonthlyDiff < 0 ? "text-success-700 dark:text-success-300" : result.totalMonthlyDiff > 0 ? "text-warning-700 dark:text-warning-300" : "text-foreground")}>
              {result.totalMonthlyDiff > 0 ? "+" : ""}
              {formatMoney(result.totalMonthlyDiff, result.currency)}
            </p>
          </div>
          <div className="flex flex-col gap-1">
            <p className="text-xs text-muted-foreground">Annual difference</p>
            <p className={cn("text-lg font-semibold", result.totalAnnualDiff < 0 ? "text-success-700 dark:text-success-300" : result.totalAnnualDiff > 0 ? "text-warning-700 dark:text-warning-300" : "text-foreground")}>
              {result.totalAnnualDiff > 0 ? "+" : ""}
              {formatMoney(result.totalAnnualDiff, result.currency)}
            </p>
          </div>
          <div className="col-span-2 flex items-center gap-2 sm:col-span-4">
            <ImpactBadge amount={result.totalMonthlyDiff} />
            <span className="text-sm text-muted-foreground">
              {result.totalPercentChange > 0 ? "+" : ""}
              {result.totalPercentChange.toFixed(1)}% vs. current, across {result.rows.length} resource{result.rows.length === 1 ? "" : "s"}
            </span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Per-resource comparison</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Resource</TableHead>
                <TableHead>Current configuration</TableHead>
                <TableHead className="text-right">Current cost</TableHead>
                <TableHead>Proposed configuration</TableHead>
                <TableHead className="text-right">Proposed cost</TableHead>
                <TableHead className="text-right">Monthly diff</TableHead>
                <TableHead className="text-right">Annual diff</TableHead>
                <TableHead className="text-right">% change</TableHead>
                <TableHead>Impact</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {result.rows.map((row) => (
                <TableRow key={row.key}>
                  <TableCell className="font-medium text-foreground">
                    <div className="flex items-center gap-1.5">
                      {row.intent === "upgrade" ? (
                        <ArrowUpCircle className="size-3.5 text-primary-600" />
                      ) : (
                        <ArrowDownCircle className="size-3.5 text-muted-foreground" />
                      )}
                      {row.displayName}
                    </div>
                  </TableCell>
                  <TableCell className="max-w-64 whitespace-normal text-xs text-muted-foreground">
                    {row.currentConfigText} &middot; Qty {row.currentQuantity}
                  </TableCell>
                  <TableCell className="text-right">{formatMoney(row.currentMonthly, row.currency)}</TableCell>
                  <TableCell className="max-w-64 whitespace-normal text-xs text-muted-foreground">
                    {row.proposedConfigText} &middot; Qty {row.proposedQuantity}
                  </TableCell>
                  <TableCell className="text-right">{formatMoney(row.proposedMonthly, row.currency)}</TableCell>
                  <TableCell className={cn("text-right", row.monthlyDiff < 0 ? "text-success-700 dark:text-success-300" : row.monthlyDiff > 0 ? "text-warning-700 dark:text-warning-300" : "")}>
                    {row.monthlyDiff > 0 ? "+" : ""}
                    {formatMoney(row.monthlyDiff, row.currency)}
                  </TableCell>
                  <TableCell className={cn("text-right", row.annualDiff < 0 ? "text-success-700 dark:text-success-300" : row.annualDiff > 0 ? "text-warning-700 dark:text-warning-300" : "")}>
                    {row.annualDiff > 0 ? "+" : ""}
                    {formatMoney(row.annualDiff, row.currency)}
                  </TableCell>
                  <TableCell className="text-right">
                    {row.percentChange > 0 ? "+" : ""}
                    {row.percentChange.toFixed(1)}%
                  </TableCell>
                  <TableCell>
                    <ImpactBadge amount={row.monthlyDiff} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function ResourceEditorCard({
  group,
  proposal,
  intent,
  onIntentChange,
  onConfigChange,
  onQuantityChange,
  onReset,
}: {
  group: ResourceGroup;
  proposal: Proposal;
  intent: "upgrade" | "downgrade";
  onIntentChange: (intent: "upgrade" | "downgrade") => void;
  onConfigChange: (config: Record<string, unknown>) => void;
  onQuantityChange: (quantity: number) => void;
  onReset: () => void;
}) {
  const Icon = group.definition ? serviceIcon(group.definition.icon) : Layers;

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          {/* `Icon` is a lookup into service-icons.ts's fixed ICONS map, not a
              component defined during render - see service-card.tsx for the
              same accepted pattern. */}
          {/* eslint-disable-next-line react-hooks/static-components */}
          <Icon className="size-4 text-muted-foreground" />
          {group.definition?.display_name ?? group.service_id}
        </CardTitle>
        <div className="flex items-center gap-2">
          <div className="flex rounded-md border border-border-strong p-0.5 text-xs">
            <button
              type="button"
              onClick={() => onIntentChange("upgrade")}
              className={cn("rounded px-2 py-1", intent === "upgrade" ? "bg-primary text-primary-foreground" : "text-muted-foreground")}
            >
              Upgrade
            </button>
            <button
              type="button"
              onClick={() => onIntentChange("downgrade")}
              className={cn("rounded px-2 py-1", intent === "downgrade" ? "bg-primary text-primary-foreground" : "text-muted-foreground")}
            >
              Downgrade
            </button>
          </div>
          <Button type="button" variant="ghost" size="sm" onClick={onReset}>
            Reset to current
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-xs text-muted-foreground">
          Current: {describeConfig(group.definition, group.originalConfig)} &middot; Qty {group.originalQuantity}
        </p>
        {group.definition ? (
          <DynamicServiceConfigForm definition={group.definition} config={proposal.config} onChange={onConfigChange} />
        ) : (
          <p className="text-xs text-muted-foreground">This service is no longer in the catalog - only its quantity can be changed.</p>
        )}
        <Field label="Proposed quantity" htmlFor={`qty-${group.key}`}>
          <Input
            id={`qty-${group.key}`}
            type="number"
            min={1}
            step={1}
            value={proposal.quantity}
            onChange={(e) => onQuantityChange(Math.max(1, Math.floor(Number(e.target.value)) || 1))}
            className="w-28"
          />
        </Field>
      </CardContent>
    </Card>
  );
}

function ResourceOptimizationContent() {
  const searchParams = useSearchParams();
  const projectParam = searchParams.get("project");
  const { formatMoney } = useCurrency();

  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(projectParam ? Number(projectParam) : null);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [proposals, setProposals] = useState<Record<string, Proposal>>({});
  const [intents, setIntents] = useState<Record<string, "upgrade" | "downgrade">>({});
  const [commitmentTermYears, setCommitmentTermYears] = useState(0);
  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [isComparing, setIsComparing] = useState(false);
  const [result, setResult] = useState<ComparisonResult | null>(null);

  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: projectsApi.list });

  const versionsQuery = useQuery({
    queryKey: ["project-versions", selectedProjectId],
    queryFn: () => projectsApi.listVersions(selectedProjectId as number),
    enabled: selectedProjectId !== null,
  });
  const versions = useMemo(() => [...(versionsQuery.data ?? [])].sort((a, b) => b.version - a.version), [versionsQuery.data]);
  const effectiveVersion = selectedVersion ?? versions[0]?.version ?? null;

  const versionDetailQuery = useQuery({
    queryKey: ["project-version-detail", selectedProjectId, effectiveVersion],
    queryFn: () => projectsApi.getVersion(selectedProjectId as number, effectiveVersion as number),
    enabled: selectedProjectId !== null && effectiveVersion !== null,
  });
  const loaded: EstimateVersionDetail | null = versionDetailQuery.data ?? null;

  const servicesQuery = useQuery({ queryKey: ["catalog-services"], queryFn: () => catalogApi.services() });
  const definitionsById = useMemo(() => {
    const map = new Map<string, GCPServiceDefinition>();
    for (const s of servicesQuery.data ?? []) map.set(s.service_id, s);
    return map;
  }, [servicesQuery.data]);

  const groups = useMemo(
    () => (loaded ? buildGroups(loaded.request.selected_services, definitionsById) : []),
    [loaded, definitionsById],
  );

  // Resets everything picked/proposed/compared whenever a different
  // project or version loads, so switching estimates never carries over a
  // stale selection or comparison result for a resource that may not even
  // exist on the newly loaded version.
  const loadedKey = loaded ? `${selectedProjectId}-${loaded.version}` : null;
  const [seededKey, setSeededKey] = useState<string | null>(null);
  if (loadedKey !== seededKey) {
    setSeededKey(loadedKey);
    setSelectedKeys(new Set());
    setProposals({});
    setIntents({});
    setResult(null);
    setValidation(null);
  }

  const selectedGroups = groups.filter((g) => selectedKeys.has(g.key));

  const previewRequirement: CustomerRequirement | null = useMemo(() => {
    if (!loaded || selectedGroups.length === 0) return null;
    const everyProposalReady = selectedGroups.every((g) => proposals[g.key]);
    if (!everyProposalReady) return null;
    return {
      ...loaded.request,
      selected_services: combinedProposedSelections(loaded.request.selected_services, groups, selectedKeys, proposals),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, groups, selectedKeys, proposals]);

  useEffect(() => {
    if (!previewRequirement) return;
    const handle = setTimeout(async () => {
      setIsValidating(true);
      try {
        setValidation(await estimateApi.validate(previewRequirement));
      } catch {
        // Preview only - a failed live-check shouldn't block editing.
      } finally {
        setIsValidating(false);
      }
    }, 500);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(previewRequirement)]);

  // Derived, not synced via the effect above: hides whatever `validation`
  // last held once there's nothing selected to preview, without a setState
  // call inside the effect body.
  const displayedValidation = previewRequirement ? validation : null;

  function handleProjectChange(value: string) {
    setSelectedProjectId(value ? Number(value) : null);
    setSelectedVersion(null);
  }

  function toggleGroup(group: ResourceGroup, checked: boolean) {
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      if (checked) next.add(group.key);
      else next.delete(group.key);
      return next;
    });
    setProposals((prev) => {
      if (prev[group.key]) return prev;
      return { ...prev, [group.key]: { config: { ...group.originalConfig }, quantity: group.originalQuantity } };
    });
    setIntents((prev) => (prev[group.key] ? prev : { ...prev, [group.key]: "downgrade" }));
    setResult(null);
  }

  function resetGroup(group: ResourceGroup) {
    setProposals((prev) => ({ ...prev, [group.key]: { config: { ...group.originalConfig }, quantity: group.originalQuantity } }));
    setResult(null);
  }

  async function runComparison() {
    if (!loaded || selectedGroups.length === 0) return;
    setIsComparing(true);
    try {
      const baseSelections = loaded.request.selected_services;
      const scenarios: ScenarioRequest[] = [];
      for (const g of selectedGroups) {
        const proposal = proposals[g.key];
        scenarios.push({ name: `without__${g.key}`, overrides: { selected_services: withoutGroup(baseSelections, g) } });
        scenarios.push({ name: `proposed__${g.key}`, overrides: { selected_services: withProposedGroup(baseSelections, g, proposal) } });
      }
      scenarios.push({
        name: "combined_proposed",
        overrides: { selected_services: combinedProposedSelections(baseSelections, groups, selectedKeys, proposals) },
      });

      const response = await optimizationApi.compareScenarios(loaded.request, scenarios, { force: true, commitmentTermYears });
      const byName = new Map(response.scenarios.map((s) => [s.name, s]));
      const base = response.base;

      const rows: ResourceComparisonRow[] = selectedGroups.map((g) => {
        const without = byName.get(`without__${g.key}`)!;
        const proposedOutcome = byName.get(`proposed__${g.key}`)!;
        const currentMonthly = round2(base.total_monthly - without.total_monthly);
        const proposedMonthly = round2(proposedOutcome.total_monthly - without.total_monthly);
        const monthlyDiff = round2(proposedMonthly - currentMonthly);
        const annualDiff = round2(monthlyDiff * 12);
        const percentChange = currentMonthly !== 0 ? round2((monthlyDiff / currentMonthly) * 100) : proposedMonthly > 0 ? 100 : 0;
        const proposal = proposals[g.key];
        return {
          key: g.key,
          displayName: g.definition?.display_name ?? g.service_id,
          currentConfigText: describeConfig(g.definition, g.originalConfig),
          proposedConfigText: describeConfig(g.definition, proposal.config),
          currentQuantity: g.originalQuantity,
          proposedQuantity: proposal.quantity,
          currentMonthly,
          proposedMonthly,
          monthlyDiff,
          annualDiff,
          percentChange,
          intent: intents[g.key] ?? "downgrade",
          currency: base.currency,
        };
      });

      const combined = byName.get("combined_proposed")!;
      setResult({
        currency: base.currency,
        rows,
        currentTotal: base.total_monthly,
        proposedTotal: combined.total_monthly,
        totalMonthlyDiff: round2(combined.delta_vs_base_monthly),
        totalAnnualDiff: round2(combined.total_yearly - base.total_yearly),
        totalPercentChange: combined.delta_vs_base_percent,
      });
      toast.success("Comparison complete");
    } catch (err) {
      toast.error("Could not run the comparison", { description: apiErrorMessage(err) });
    } finally {
      setIsComparing(false);
    }
  }

  const hasBlockers = displayedValidation?.results.some((r) => r.severity === "blocker") ?? false;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Resource Optimization</h1>
        <p className="text-sm text-muted-foreground">
          Pick resources from a saved estimate and compare their current configuration/cost against a proposed
          upgrade or downgrade - priced through the same pipeline as every other estimate on this platform.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Estimate to optimize</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="project-select">Project</Label>
            <Select id="project-select" value={selectedProjectId ?? ""} onChange={(e) => handleProjectChange(e.target.value)}>
              <option value="">Select a project...</option>
              {projectsQuery.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="version-select">Estimate version</Label>
            <Select
              id="version-select"
              value={effectiveVersion ?? ""}
              onChange={(e) => setSelectedVersion(e.target.value ? Number(e.target.value) : null)}
              disabled={selectedProjectId === null || versions.length === 0}
            >
              {versions.map((v) => (
                <option key={v.version} value={v.version}>
                  v{v.version} - {formatMoney(v.total_monthly, v.currency)}/mo
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      {selectedProjectId !== null && !versionsQuery.isLoading && versions.length === 0 && (
        <EmptyState
          icon={FolderSearch}
          title="No saved estimate yet"
          description="This project has no estimate version to optimize. Save an estimate to this project first."
          action={
            <Link href="/estimate/new" className={cn(buttonVariants({ size: "sm" }))}>
              Go to New Estimate
            </Link>
          }
        />
      )}

      {versionDetailQuery.isLoading && effectiveVersion !== null && (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {loaded && groups.length === 0 && (
        <EmptyState
          icon={Layers}
          title="No catalog resources on this estimate"
          description="Resource Optimization compares GCP-service-catalog resources. Add one or more services to this estimate first."
          action={
            <Link href={`/estimate/existing?project=${selectedProjectId}`} className={cn(buttonVariants({ size: "sm" }))}>
              Add services
            </Link>
          }
        />
      )}

      {loaded && groups.length > 0 && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="flex flex-col gap-4 lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Resources on v{loaded.version} ({groups.length})</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {groups.map((g) => {
                  const Icon = g.definition ? serviceIcon(g.definition.icon) : Layers;
                  return (
                    <label key={g.key} className="flex items-start gap-3 rounded-md border border-border p-3">
                      <Checkbox
                        checked={selectedKeys.has(g.key)}
                        onChange={(e) => toggleGroup(g, e.target.checked)}
                        className="mt-0.5"
                      />
                      <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                      <div className="flex flex-1 flex-col gap-0.5">
                        <span className="text-sm font-medium text-foreground">{g.definition?.display_name ?? g.service_id}</span>
                        <span className="text-xs text-muted-foreground">
                          {describeConfig(g.definition, g.originalConfig)} &middot; Qty {g.originalQuantity}
                        </span>
                      </div>
                      {g.definition?.category && <Badge variant="secondary">{g.definition.category}</Badge>}
                    </label>
                  );
                })}
              </CardContent>
            </Card>

            {selectedGroups.map((g) => {
              const proposal = proposals[g.key];
              if (!proposal) return null;
              return (
                <ResourceEditorCard
                  key={g.key}
                  group={g}
                  proposal={proposal}
                  intent={intents[g.key] ?? "downgrade"}
                  onIntentChange={(intent) => setIntents((prev) => ({ ...prev, [g.key]: intent }))}
                  onConfigChange={(config) => {
                    setProposals((prev) => ({ ...prev, [g.key]: { ...prev[g.key], config } }));
                    setResult(null);
                  }}
                  onQuantityChange={(quantity) => {
                    setProposals((prev) => ({ ...prev, [g.key]: { ...prev[g.key], quantity } }));
                    setResult(null);
                  }}
                  onReset={() => resetGroup(g)}
                />
              );
            })}
          </div>

          <div className="flex flex-col gap-4">
            <Card className="sticky top-20">
              <CardHeader>
                <CardTitle className="text-sm">Compare</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="commitment">Pricing preference</Label>
                  <Select id="commitment" value={commitmentTermYears} onChange={(e) => setCommitmentTermYears(Number(e.target.value))}>
                    <option value={0}>On-demand (Sustained Use Discount)</option>
                    <option value={1}>1-year Committed Use Discount</option>
                    <option value={3}>3-year Committed Use Discount</option>
                  </Select>
                </div>

                {selectedGroups.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Select one or more resources on the left to propose a change.</p>
                ) : (
                  <ValidationPanel report={displayedValidation} isLoading={isValidating} />
                )}

                <Button onClick={runComparison} disabled={isComparing || selectedGroups.length === 0}>
                  {isComparing && <Spinner />}
                  Compare {selectedGroups.length > 0 ? `${selectedGroups.length} resource${selectedGroups.length === 1 ? "" : "s"}` : ""}
                </Button>
                {hasBlockers && <p className="text-xs text-warning-700 dark:text-warning-300">Comparing forces through validation blockers, same as a preview elsewhere on this platform.</p>}
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {result && <ComparisonResultsView result={result} />}
    </div>
  );
}

export default function ResourceOptimizationPage() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <ResourceOptimizationContent />
    </Suspense>
  );
}
