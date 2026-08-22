"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { FolderSearch } from "lucide-react";
import { toast } from "sonner";

import { EstimateResultView } from "@/components/estimate-result-view";
import { OptimizationPanel } from "@/components/finops/optimization-panel";
import { SaveToProjectDialog } from "@/components/save-to-project-dialog";
import { ServiceCatalogBrowser } from "@/components/service-catalog/service-catalog-browser";
import { SelectedServicesPanel } from "@/components/service-catalog/selected-services-panel";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ValidationPanel } from "@/components/validation-panel";
import { NetworkStep, SizingStep, StorageStep } from "@/components/wizard/steps";
import { emptyRequirement, useWizardState } from "@/components/wizard/use-wizard-state";
import { useServiceSelection } from "@/components/wizard/use-service-selection";
import { useSetAssistantEstimate } from "@/contexts/assistant-context";
import { useCurrency } from "@/contexts/currency-context";
import { apiErrorMessage, catalogApi, estimateApi, projectsApi } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type {
  CustomerRequirement,
  EstimateResult,
  EstimateVersionDetail,
  GCPServiceDefinition,
  ServiceSelection,
  ValidationReport,
} from "@/lib/types";

type Mode = "update" | "quick";

// Compute Engine is always sized via the Sizing card on each tab, same as
// the New Estimate page - its catalog card is browsable for discoverability
// but never independently configurable, so it never becomes a
// selected_services entry with an empty/no-op config.
const COMPUTE_ENGINE_SERVICE_ID = "compute-engine";

/** Adds/replaces `incoming` selections into `base` by `service_id`, leaving
 * every other selection - and every non-catalog field of the requirement -
 * untouched. This is what makes "Existing Estimate" only (re)calculate the
 * service(s) the user actually picked, instead of re-running the full
 * Basics/Sizing wizard against everything already on the estimate. */
function upsertServiceSelections(base: ServiceSelection[], incoming: ServiceSelection[]): ServiceSelection[] {
  const merged = [...base];
  for (const item of incoming) {
    const idx = merged.findIndex((s) => s.service_id === item.service_id);
    if (idx >= 0) merged[idx] = item;
    else merged.push(item);
  }
  return merged;
}

function ExistingEstimateContent() {
  const searchParams = useSearchParams();
  const projectParam = searchParams.get("project");
  const { formatMoney } = useCurrency();

  const [mode, setMode] = useState<Mode>("update");

  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(
    projectParam ? Number(projectParam) : null,
  );
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const selection = useServiceSelection();

  // Compute Engine sizing (machine family/vCPU/RAM, provisioning model, OS,
  // running duration, GPU) for each tab - kept separate from `selection`
  // since Compute Engine is never a catalog ServiceSelection (its card is a
  // no-op placeholder; see getAddState below), it's a top-level
  // CustomerRequirement.compute field like every other wizard entry point.
  const updateSizing = useWizardState();
  const quickSizing = useWizardState();
  // Starts collapsed whenever the loaded version already has a Compute
  // Engine config, so adding an unrelated service (e.g. Vertex AI) to an
  // existing estimate doesn't put its sizing back in front of the user by
  // default - it's still one click away via "Edit sizing", never re-asked.
  // `sizingManuallyExpanded` is reset by comparing against the last-seeded
  // version key *during render* (React's documented pattern for resetting
  // state on a prop/data change) rather than in a useEffect, since setState
  // synchronously inside an effect body is a lint error here.
  const [sizingManuallyExpanded, setSizingManuallyExpanded] = useState(false);
  const [sizingSeededKey, setSizingSeededKey] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [commitmentTermYears, setCommitmentTermYears] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [updated, setUpdated] = useState<EstimateVersionDetail | null>(null);
  const [quickResult, setQuickResult] = useState<EstimateResult | null>(null);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  useSetAssistantEstimate(quickResult ?? updated?.result ?? null);

  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: projectsApi.list });

  const versionsQuery = useQuery({
    queryKey: ["project-versions", selectedProjectId],
    queryFn: () => projectsApi.listVersions(selectedProjectId as number),
    enabled: selectedProjectId !== null,
  });
  const versions = useMemo(
    () => [...(versionsQuery.data ?? [])].sort((a, b) => b.version - a.version),
    [versionsQuery.data],
  );

  // Default to the latest saved version whenever nothing is explicitly
  // selected yet - a derived value, not synced state, so switching projects
  // (which resets selectedVersion to null) doesn't need an effect.
  const effectiveVersion = selectedVersion ?? versions[0]?.version ?? null;

  const versionDetailQuery = useQuery({
    queryKey: ["project-version-detail", selectedProjectId, effectiveVersion],
    queryFn: () => projectsApi.getVersion(selectedProjectId as number, effectiveVersion as number),
    enabled: mode === "update" && selectedProjectId !== null && effectiveVersion !== null,
  });
  const loaded = versionDetailQuery.data ?? null;

  // Seed the Sizing card from whatever this saved version already has
  // whenever the loaded project/version changes, so editing an existing
  // estimate's Compute Engine config starts from its current values instead
  // of a blank form. Runs on `loaded.version`/`selectedProjectId` (not the
  // whole `loaded` object) so it doesn't re-fire on every keystroke made in
  // the Sizing card itself.
  useEffect(() => {
    if (!loaded) return;
    if (loaded.request.compute) {
      updateSizing.setSizing("explicit");
      updateSizing.update("compute", loaded.request.compute);
      if (loaded.request.storage) updateSizing.update("storage", loaded.request.storage);
      if (loaded.request.network) updateSizing.update("network", loaded.request.network);
    } else if (loaded.request.business) {
      updateSizing.setSizing("business");
      updateSizing.update("business", loaded.request.business);
    } else {
      updateSizing.setSizing("none");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProjectId, loaded?.version]);

  // Reset the manual "Edit sizing" override whenever a different version
  // loads, so each newly-loaded version starts collapsed again if it has an
  // existing compute config - set during render (React's documented pattern
  // for resetting state on a data change), not inside the effect above.
  const currentSizingKey = loaded ? `${selectedProjectId}-${loaded.version}` : null;
  if (currentSizingKey !== sizingSeededKey) {
    setSizingSeededKey(currentSizingKey);
    setSizingManuallyExpanded(false);
  }
  const sizingExpanded = sizingManuallyExpanded || !loaded?.request.compute;

  const servicesQuery = useQuery({ queryKey: ["catalog-services"], queryFn: () => catalogApi.services() });
  const definitionsById = useMemo(() => {
    const map = new Map<string, GCPServiceDefinition>();
    for (const s of servicesQuery.data ?? []) map.set(s.service_id, s);
    return map;
  }, [servicesQuery.data]);

  const fullRequirement: CustomerRequirement | null = useMemo(() => {
    if (!loaded) return null;
    return {
      ...loaded.request,
      compute: updateSizing.requirement.compute,
      business: updateSizing.requirement.business,
      storage: updateSizing.requirement.storage ?? loaded.request.storage,
      network: updateSizing.requirement.network ?? loaded.request.network,
      selected_services: upsertServiceSelections(loaded.request.selected_services, selection.asServiceSelections),
    };
  }, [
    loaded,
    selection.asServiceSelections,
    updateSizing.requirement.compute,
    updateSizing.requirement.business,
    updateSizing.requirement.storage,
    updateSizing.requirement.network,
  ]);

  // No project needed: prices just the picked service(s) - and, if the
  // Sizing card below is used, a Compute Engine instance - against defaulted
  // basics, for someone who wants a number without the full Basics/Sizing
  // wizard or an existing saved estimate.
  const quickRequirement: CustomerRequirement = useMemo(
    () => ({
      ...emptyRequirement(),
      project_name: "Quick calculation",
      compute: quickSizing.requirement.compute,
      business: quickSizing.requirement.business,
      storage: quickSizing.requirement.storage,
      network: quickSizing.requirement.network,
      selected_services: selection.asServiceSelections,
    }),
    [
      selection.asServiceSelections,
      quickSizing.requirement.compute,
      quickSizing.requirement.business,
      quickSizing.requirement.storage,
      quickSizing.requirement.network,
    ],
  );

  const activeRequirement = mode === "quick" ? quickRequirement : fullRequirement;

  // "Content" here means something has actually been added beyond the two
  // tabs' bare defaults - either a catalog service, or a Compute Engine
  // config entered in the Sizing card above. Gates both live validation and
  // the submit buttons so neither fires against an empty/no-op request.
  const hasQuickContent = selection.entries.length > 0 || !!quickSizing.requirement.compute || !!quickSizing.requirement.business;
  const hasUpdateContent = selection.entries.length > 0 || !!updateSizing.requirement.compute || !!updateSizing.requirement.business;

  useEffect(() => {
    if (!activeRequirement) return;
    if (mode === "quick" && !hasQuickContent) return; // nothing to validate yet - displayedValidation below hides any stale result
    const handle = setTimeout(async () => {
      setIsValidating(true);
      try {
        setValidation(await estimateApi.validate(activeRequirement));
      } catch {
        // Preview only - a failed live-check shouldn't block editing.
      } finally {
        setIsValidating(false);
      }
    }, 500);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, JSON.stringify(activeRequirement)]);

  // Derived, not synced via an effect: hides whatever `validation` last held
  // once the quick tab has nothing left to validate, without a setState
  // call inside the effect above.
  const displayedValidation = mode === "quick" && !hasQuickContent ? null : validation;
  const hasBlockers = displayedValidation?.results.some((r) => r.severity === "blocker") ?? false;

  function getAddState(definition: GCPServiceDefinition): { disabled: boolean; label?: string } {
    if (definition.service_id === COMPUTE_ENGINE_SERVICE_ID) {
      return { disabled: true, label: "Configured via Sizing" };
    }
    if (definition.legacy_binding && selection.selectedServiceIds.has(definition.service_id)) {
      return { disabled: true, label: "Already added" };
    }
    return { disabled: false };
  }

  function canDuplicate(definition: GCPServiceDefinition): boolean {
    return definition.legacy_binding === null;
  }

  function handleProjectChange(value: string) {
    setSelectedProjectId(value ? Number(value) : null);
    setSelectedVersion(null);
    setUpdated(null);
  }

  function handleModeChange(value: string) {
    setMode(value as Mode);
    setValidation(null);
  }

  async function handleSubmit(force: boolean) {
    if (!selectedProjectId || !fullRequirement) return;
    setIsSubmitting(true);
    try {
      const version = await projectsApi.createEstimateVersion(selectedProjectId, fullRequirement, {
        force,
        commitmentTermYears,
      });
      setUpdated(version);
      toast.success(`Estimate updated to v${version.version}`);
    } catch (err) {
      toast.error("Could not update this estimate", { description: apiErrorMessage(err) });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleQuickCalculate(force: boolean) {
    setIsSubmitting(true);
    try {
      const priced = await estimateApi.create(quickRequirement, { force, commitmentTermYears });
      setQuickResult(priced);
      toast.success("Estimate calculated");
    } catch (err) {
      toast.error("Could not price this configuration", { description: apiErrorMessage(err) });
    } finally {
      setIsSubmitting(false);
    }
  }

  if (mode === "update" && updated) {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-foreground">{updated.result.project_name}</h1>
            <p className="text-sm text-muted-foreground">
              Updated to v{updated.version} - {formatMoney(updated.total_monthly, updated.currency)}/mo
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setUpdated(null)}>
              Add more services
            </Button>
            <Link
              href={`/projects/${selectedProjectId}/estimates/${updated.version}`}
              className={cn(buttonVariants({ size: "sm" }))}
            >
              View in project
            </Link>
          </div>
        </div>
        <EstimateResultView result={updated.result} />
        <OptimizationPanel requirement={updated.request} />
      </div>
    );
  }

  if (mode === "quick" && quickResult) {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-foreground">{quickResult.project_name}</h1>
            <p className="text-sm text-muted-foreground">Priced instantly - nothing here is a preview approximation.</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setQuickResult(null)}>
              Calculate more
            </Button>
            <Button size="sm" onClick={() => setSaveDialogOpen(true)}>
              Save to a project
            </Button>
          </div>
        </div>
        <EstimateResultView result={quickResult} />
        <OptimizationPanel requirement={quickRequirement} />
        <SaveToProjectDialog
          open={saveDialogOpen}
          onOpenChange={setSaveDialogOpen}
          requirement={quickRequirement}
          commitmentTermYears={commitmentTermYears}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Existing estimate</h1>
        <p className="text-sm text-muted-foreground">
          Pick a saved estimate to update its Compute Engine sizing and/or add GCP services, or skip project
          selection entirely and price a configuration on its own.
        </p>
      </div>

      <Tabs value={mode} onValueChange={handleModeChange}>
        <TabsList>
          <TabsTrigger value="update">Update a saved estimate</TabsTrigger>
          <TabsTrigger value="quick">Quick calculate (no project)</TabsTrigger>
        </TabsList>

        <TabsContent value="update" className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Estimate to update</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="project-select">Project</Label>
                <Select
                  id="project-select"
                  value={selectedProjectId ?? ""}
                  onChange={(e) => handleProjectChange(e.target.value)}
                >
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
              description="This project has no estimate version to update. Start with New Estimate and save it to this project first."
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

          {loaded && (
            <>
              <Card>
                <CardContent className="flex flex-col gap-1 pt-5 text-sm text-muted-foreground">
                  <p>
                    Currently <span className="font-medium text-foreground">{formatMoney(loaded.total_monthly, loaded.currency)}/mo</span> across{" "}
                    {loaded.request.selected_services.length} catalog service{loaded.request.selected_services.length === 1 ? "" : "s"} on v{loaded.version}.
                    Sizing is pre-filled from this version - edit it and/or add services below, everything else stays as it is.
                  </p>
                </CardContent>
              </Card>

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                <div className="flex flex-col gap-4 lg:col-span-2">
                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between gap-2">
                      <CardTitle className="text-sm">Compute Engine sizing</CardTitle>
                      {loaded.request.compute && !sizingExpanded && (
                        <Button variant="ghost" size="sm" onClick={() => setSizingManuallyExpanded(true)}>
                          Edit sizing
                        </Button>
                      )}
                    </CardHeader>
                    <CardContent>
                      {loaded.request.compute && !sizingExpanded ? (
                        <p className="text-sm text-muted-foreground">
                          Unchanged from v{loaded.version} - {loaded.request.compute.instance_count}x{" "}
                          {loaded.request.compute.vcpu} vCPU / {loaded.request.compute.ram_gb} GB (
                          {loaded.request.compute.machine_family}). Adding a service below does not touch this.
                        </p>
                      ) : (
                        <div className="flex flex-col gap-5">
                          <SizingStep state={updateSizing} />
                          {updateSizing.sizingMode === "explicit" && (
                            <>
                              <StorageStep state={updateSizing} />
                              <NetworkStep state={updateSizing} />
                            </>
                          )}
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">GCP service catalog</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ServiceCatalogBrowser
                        getSelectedCount={(id) => selection.entries.filter((e) => e.service_id === id).length}
                        getAddState={getAddState}
                        onAddService={(definition) => selection.addService(definition)}
                      />
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Services to add or update</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <SelectedServicesPanel
                        entries={selection.entries}
                        definitionsById={definitionsById}
                        validation={displayedValidation}
                        canDuplicate={canDuplicate}
                        onUpdateConfig={selection.updateServiceConfig}
                        onUpdateQuantity={selection.updateServiceQuantity}
                        onRemove={selection.removeService}
                        onDuplicate={selection.duplicateService}
                      />
                    </CardContent>
                  </Card>
                </div>

                <div className="flex flex-col gap-4">
                  <Card className="sticky top-20">
                    <CardHeader>
                      <CardTitle className="text-sm">Update it</CardTitle>
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

                      <ValidationPanel report={displayedValidation} isLoading={isValidating} />

                      <div className="flex flex-col gap-2">
                        {hasBlockers && (
                          <Button variant="secondary" onClick={() => handleSubmit(true)} disabled={isSubmitting || !hasUpdateContent}>
                            {isSubmitting && <Spinner />}
                            Force through blockers
                          </Button>
                        )}
                        <Button onClick={() => handleSubmit(false)} disabled={isSubmitting || hasBlockers || !hasUpdateContent}>
                          {isSubmitting && <Spinner />}
                          Update existing estimate
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </>
          )}
        </TabsContent>

        <TabsContent value="quick" className="flex flex-col gap-6">
          <p className="text-sm text-muted-foreground">
            No project or estimate version needed - pick the GCP service(s) you need a number for and price them
            directly.
          </p>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="flex flex-col gap-4 lg:col-span-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Sizing</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-5">
                  <SizingStep state={quickSizing} />
                  {quickSizing.sizingMode === "explicit" && (
                    <>
                      <StorageStep state={quickSizing} />
                      <NetworkStep state={quickSizing} />
                    </>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">GCP service catalog</CardTitle>
                </CardHeader>
                <CardContent>
                  <ServiceCatalogBrowser
                    getSelectedCount={(id) => selection.entries.filter((e) => e.service_id === id).length}
                    getAddState={getAddState}
                    onAddService={(definition) => selection.addService(definition)}
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Services to price</CardTitle>
                </CardHeader>
                <CardContent>
                  <SelectedServicesPanel
                    entries={selection.entries}
                    definitionsById={definitionsById}
                    validation={displayedValidation}
                    canDuplicate={canDuplicate}
                    onUpdateConfig={selection.updateServiceConfig}
                    onUpdateQuantity={selection.updateServiceQuantity}
                    onRemove={selection.removeService}
                    onDuplicate={selection.duplicateService}
                  />
                </CardContent>
              </Card>
            </div>

            <div className="flex flex-col gap-4">
              <Card className="sticky top-20">
                <CardHeader>
                  <CardTitle className="text-sm">Calculate</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="quick-commitment">Pricing preference</Label>
                    <Select id="quick-commitment" value={commitmentTermYears} onChange={(e) => setCommitmentTermYears(Number(e.target.value))}>
                      <option value={0}>On-demand (Sustained Use Discount)</option>
                      <option value={1}>1-year Committed Use Discount</option>
                      <option value={3}>3-year Committed Use Discount</option>
                    </Select>
                  </div>

                  <ValidationPanel report={displayedValidation} isLoading={isValidating} />

                  <div className="flex flex-col gap-2">
                    {hasBlockers && (
                      <Button variant="secondary" onClick={() => handleQuickCalculate(true)} disabled={isSubmitting || !hasQuickContent}>
                        {isSubmitting && <Spinner />}
                        Force through blockers
                      </Button>
                    )}
                    <Button onClick={() => handleQuickCalculate(false)} disabled={isSubmitting || hasBlockers || !hasQuickContent}>
                      {isSubmitting && <Spinner />}
                      Calculate
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default function ExistingEstimatePage() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <ExistingEstimateContent />
    </Suspense>
  );
}
