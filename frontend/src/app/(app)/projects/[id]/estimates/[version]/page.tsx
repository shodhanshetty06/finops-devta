"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertOctagon } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { EstimateResultView } from "@/components/estimate-result-view";
import { ExportButtons } from "@/components/export-buttons";
import { OptimizationPanel } from "@/components/finops/optimization-panel";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useSetAssistantEstimate } from "@/contexts/assistant-context";
import { apiErrorMessage, projectsApi } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";

function EstimateDashboard({ projectId, version }: { projectId: number; version: number }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["estimate-version", projectId, version],
    queryFn: () => projectsApi.getVersion(projectId, version),
  });
  useSetAssistantEstimate(data?.result ?? null);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-10 w-80" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  if (isError || !data) {
    return <EmptyState icon={AlertOctagon} title="Couldn't load this estimate" description={apiErrorMessage(error)} />;
  }

  const { result } = data;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm text-muted-foreground">
            <Link href={`/projects/${projectId}`} className="hover:text-foreground hover:underline">
              {result.project_name}
            </Link>{" "}
            &rsaquo; version {data.version}
          </p>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">Cost estimate</h1>
          <p className="text-xs text-muted-foreground">
            Generated {formatDate(data.created_at)} &middot; strategy: {result.strategy_used} &middot; region:{" "}
            {result.normalized_spec.region}
          </p>
        </div>
        <ExportButtons projectId={projectId} version={version} projectName={result.project_name} />
      </div>

      <EstimateResultView result={result} />
      <OptimizationPanel requirement={data.request} />
    </div>
  );
}

export default function EstimateVersionPage() {
  const params = useParams<{ id: string; version: string }>();
  return <EstimateDashboard projectId={Number(params.id)} version={Number(params.version)} />;
}
