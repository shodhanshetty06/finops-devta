"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { EstimateResultView } from "@/components/estimate-result-view";
import { OptimizationPanel } from "@/components/finops/optimization-panel";
import { SaveToProjectDialog } from "@/components/save-to-project-dialog";
import { ServiceCatalogBrowser } from "@/components/service-catalog/service-catalog-browser";
import { SelectedServicesPanel } from "@/components/service-catalog/selected-services-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { ValidationPanel } from "@/components/validation-panel";
import { BasicsStep, NetworkStep, SizingStep, StorageStep } from "@/components/wizard/steps";
import { useWizardState } from "@/components/wizard/use-wizard-state";
import { useServiceSelection } from "@/components/wizard/use-service-selection";
import { useCurrency } from "@/contexts/currency-context";
import { apiErrorMessage, catalogApi, estimateApi } from "@/lib/api-client";
import type { CustomerRequirement, EstimateResult, GCPServiceDefinition, ValidationReport } from "@/lib/types";

// Compute Engine is always sized via the untouched Sizing section above -
// its catalog card is browsable for discoverability but never independently
// configurable, so it never becomes a selected_services entry.
const COMPUTE_ENGINE_SERVICE_ID = "compute-engine";

export default function NewEstimatePage() {
  const wizard = useWizardState();
  const { requirement } = wizard;
  const selection = useServiceSelection();
  const { displayCurrency, setDisplayCurrency, supportedCurrencies } = useCurrency();

  const servicesQuery = useQuery({ queryKey: ["catalog-services"], queryFn: () => catalogApi.services() });
  const definitionsById = useMemo(() => {
    const map = new Map<string, GCPServiceDefinition>();
    for (const s of servicesQuery.data ?? []) map.set(s.service_id, s);
    return map;
  }, [servicesQuery.data]);

  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [commitmentTermYears, setCommitmentTermYears] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<EstimateResult | null>(null);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);

  // A project name is never required to price a workload - most people just
  // have requirements, not a project yet. If the Basics field is left
  // blank, a stable placeholder (generated once per visit) stands in so the
  // estimate can still be generated; it's only ever shown to the user if
  // they choose to save this to a project later.
  const [defaultProjectName] = useState(() => `Quick Estimate ${new Date().toLocaleString()}`);

  const fullRequirement: CustomerRequirement = useMemo(
    () => ({
      ...requirement,
      project_name: requirement.project_name.trim() || defaultProjectName,
      selected_services: selection.asServiceSelections,
    }),
    [requirement, defaultProjectName, selection.asServiceSelections],
  );

  useEffect(() => {
    const handle = setTimeout(async () => {
      setIsValidating(true);
      try {
        setValidation(await estimateApi.validate(fullRequirement));
      } catch {
        // Preview only - a failed live-check shouldn't block typing.
      } finally {
        setIsValidating(false);
      }
    }, 500);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(fullRequirement)]);

  const displayedValidation = validation;
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

  async function handleSubmit(force: boolean) {
    setIsSubmitting(true);
    try {
      const priced = await estimateApi.create(fullRequirement, { force, commitmentTermYears });
      setResult(priced);
      toast.success("Estimate generated");
    } catch (err) {
      toast.error("Could not price this configuration", { description: apiErrorMessage(err) });
    } finally {
      setIsSubmitting(false);
    }
  }

  if (result) {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-foreground">{result.project_name}</h1>
            <p className="text-sm text-muted-foreground">Priced instantly - nothing here is a preview approximation.</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setResult(null)}>
              Start over
            </Button>
            <Button size="sm" onClick={() => setSaveDialogOpen(true)}>
              Save to a project
            </Button>
          </div>
        </div>
        <EstimateResultView result={result} />
        <OptimizationPanel requirement={fullRequirement} />
        <SaveToProjectDialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen} requirement={fullRequirement} commitmentTermYears={commitmentTermYears} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">New estimate</h1>
        <p className="text-sm text-muted-foreground">
          Search the GCP service catalog, add what this workload needs, then price it - Validation, Normalization,
          Pricing, Architecture, and Reports pick up from here unchanged.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-4 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Basics</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <BasicsStep state={wizard} />
              <div className="flex flex-col gap-1.5 sm:max-w-xs">
                <Label htmlFor="currency">Currency</Label>
                <Select id="currency" value={displayCurrency} onChange={(e) => setDisplayCurrency(e.target.value)}>
                  {supportedCurrencies.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
                <p className="text-xs text-muted-foreground">Display only - pricing is always resolved by the Pricing engine, then converted for viewing.</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Sizing</CardTitle>
            </CardHeader>
            <CardContent>
              <SizingStep state={wizard} />
            </CardContent>
          </Card>

          {wizard.sizingMode === "explicit" && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Storage &amp; networking</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-5">
                <StorageStep state={wizard} />
                <NetworkStep state={wizard} />
              </CardContent>
            </Card>
          )}

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
              <CardTitle className="text-sm">Selected services</CardTitle>
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
              <CardTitle className="text-sm">Price it</CardTitle>
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
                  <Button variant="secondary" onClick={() => handleSubmit(true)} disabled={isSubmitting}>
                    {isSubmitting && <Spinner />}
                    Force through blockers
                  </Button>
                )}
                <Button onClick={() => handleSubmit(false)} disabled={isSubmitting || hasBlockers}>
                  {isSubmitting && <Spinner />}
                  Generate estimate
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
