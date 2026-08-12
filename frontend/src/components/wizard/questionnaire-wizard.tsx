"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { SaveToProjectDialog } from "@/components/save-to-project-dialog";
import { Stepper } from "@/components/stepper";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { ValidationPanel } from "@/components/validation-panel";
import {
  AvailabilityStep,
  BasicsStep,
  DatabaseStep,
  KubernetesStep,
  NetworkStep,
  SizingStep,
  StorageStep,
} from "@/components/wizard/steps";
import { WIZARD_STEPS, useWizardState } from "@/components/wizard/use-wizard-state";
import { EstimateResultView } from "@/components/estimate-result-view";
import { apiErrorMessage, estimateApi, projectsApi } from "@/lib/api-client";
import type { EstimateResult, ValidationReport } from "@/lib/types";

/** The 7-step guided requirement wizard. Used both project-scoped
 * (`/projects/[id]/new` - saves directly as a new version and redirects)
 * and standalone (`/questionnaire` - prices statelessly and shows the
 * result inline, with an option to save it into a project afterward). */
export function QuestionnaireWizard({ projectId }: { projectId?: number }) {
  const router = useRouter();
  const state = useWizardState();
  const { requirement, stepIndex, currentStepName, goNext, goBack, goToStep } = state;

  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [commitmentTermYears, setCommitmentTermYears] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [standaloneResult, setStandaloneResult] = useState<EstimateResult | null>(null);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);

  useEffect(() => {
    if (!requirement.project_name) {
      return;
    }
    const handle = setTimeout(async () => {
      setIsValidating(true);
      try {
        const report = await estimateApi.validate(requirement);
        setValidation(report);
      } catch {
        // Validation is a convenience preview - a failure here shouldn't
        // block the user from continuing to fill out the form.
      } finally {
        setIsValidating(false);
      }
    }, 500);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(requirement)]);

  const displayedValidation = requirement.project_name ? validation : null;
  const hasBlockers = displayedValidation?.results.some((r) => r.severity === "blocker") ?? false;

  async function handleSubmit(force: boolean) {
    setIsSubmitting(true);
    try {
      if (projectId) {
        const version = await projectsApi.createEstimateVersion(projectId, requirement, { force, commitmentTermYears });
        toast.success(`Estimate v${version.version} created`);
        router.push(`/projects/${projectId}/estimates/${version.version}`);
      } else {
        const result = await estimateApi.create(requirement, { force, commitmentTermYears });
        setStandaloneResult(result);
        toast.success("Estimate generated");
      }
    } catch (err) {
      toast.error("Could not create estimate", { description: apiErrorMessage(err) });
    } finally {
      setIsSubmitting(false);
    }
  }

  const isLastStep = stepIndex === WIZARD_STEPS.length - 1;
  const canGoNext = currentStepName !== "Basics" || requirement.project_name.trim().length > 0;

  if (standaloneResult) {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">Priced with the same pipeline as every saved estimate - nothing here is a preview approximation.</p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setStandaloneResult(null)}>
              Start over
            </Button>
            <Button size="sm" onClick={() => setSaveDialogOpen(true)}>
              Save to a project
            </Button>
          </div>
        </div>
        <EstimateResultView result={standaloneResult} />
        <SaveToProjectDialog
          open={saveDialogOpen}
          onOpenChange={setSaveDialogOpen}
          requirement={requirement}
          commitmentTermYears={commitmentTermYears}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <Stepper steps={WIZARD_STEPS} currentIndex={stepIndex} onStepClick={goToStep} />
        </CardHeader>
        <CardContent>
          <CardTitle className="mb-4">{currentStepName}</CardTitle>
          {currentStepName === "Basics" && <BasicsStep state={state} />}
          {currentStepName === "Sizing" && <SizingStep state={state} />}
          {currentStepName === "Storage" && <StorageStep state={state} />}
          {currentStepName === "Database" && <DatabaseStep state={state} />}
          {currentStepName === "Network" && <NetworkStep state={state} />}
          {currentStepName === "Kubernetes" && <KubernetesStep state={state} />}
          {currentStepName === "Availability" && <AvailabilityStep state={state} />}
          {currentStepName === "Review" && (
            <div className="flex flex-col gap-4">
              <p className="text-sm text-muted-foreground">
                Review the live validation results below, choose a commitment term, and submit to price this
                configuration{projectId ? ". This will be saved as a new version of the project." : "."}
              </p>
              <div className="flex flex-col gap-1.5 sm:w-64">
                <Label htmlFor="commitment">Commitment term</Label>
                <Select
                  id="commitment"
                  value={commitmentTermYears}
                  onChange={(e) => setCommitmentTermYears(Number(e.target.value))}
                >
                  <option value={0}>On-demand (Sustained Use Discount)</option>
                  <option value={1}>1-year Committed Use Discount</option>
                  <option value={3}>3-year Committed Use Discount</option>
                </Select>
              </div>
            </div>
          )}
        </CardContent>
        <CardFooter className="justify-between">
          <Button variant="outline" onClick={goBack} disabled={stepIndex === 0}>
            Back
          </Button>
          {isLastStep ? (
            <div className="flex gap-2">
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
          ) : (
            <Button onClick={goNext} disabled={!canGoNext}>
              Next
            </Button>
          )}
        </CardFooter>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Live validation</CardTitle>
        </CardHeader>
        <CardContent>
          <ValidationPanel report={displayedValidation} isLoading={isValidating} />
        </CardContent>
      </Card>
    </div>
  );
}
