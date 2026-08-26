"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";

import { QuestionnaireWizard } from "@/components/wizard/questionnaire-wizard";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { apiErrorMessage, projectsApi } from "@/lib/api-client";
import { AlertOctagon } from "lucide-react";

export default function NewEstimatePage() {
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);
  // "Edit & recalculate" (see the estimate version page) links here with
  // ?from=<version> - fetches that one version's requirement as a fresh,
  // standalone starting point. Submitting always creates a brand new
  // version from it; the source version is never touched, and no other
  // version's resources are ever pulled in.
  const fromVersion = Number(useSearchParams().get("from"));

  const versionQuery = useQuery({
    queryKey: ["estimate-version", projectId, fromVersion],
    queryFn: () => projectsApi.getVersion(projectId, fromVersion),
    enabled: Number.isFinite(fromVersion) && fromVersion > 0,
  });

  if (versionQuery.isLoading) {
    return <Skeleton className="h-96 w-full" />;
  }
  if (versionQuery.isError) {
    return <EmptyState icon={AlertOctagon} title="Couldn't load that estimate to edit" description={apiErrorMessage(versionQuery.error)} />;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          {versionQuery.data ? `Edit estimate (from v${versionQuery.data.version})` : "New estimate"}
        </h1>
        <p className="text-sm text-muted-foreground">
          {versionQuery.data
            ? "Change whatever this workload needs, then recalculate - this saves as a new version and never modifies the original."
            : "Answer the questionnaire to generate a priced, validated estimate."}
        </p>
      </div>
      <QuestionnaireWizard projectId={projectId} initial={versionQuery.data?.request} />
    </div>
  );
}
