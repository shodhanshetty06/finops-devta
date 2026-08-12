"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ExportButtons } from "@/components/export-buttons";
import { CostCard } from "@/components/finops/cost-card";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { projectsApi } from "@/lib/api-client";
import { cn, formatDate } from "@/lib/utils";

export default function ReportsPage() {
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: projectsApi.list });
  const projectsWithEstimates = (projectsQuery.data ?? []).filter((p) => p.latest_version);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const projectId = selectedProjectId ?? projectsWithEstimates[0]?.id ?? null;

  const versionsQuery = useQuery({
    queryKey: ["project-versions", projectId],
    queryFn: () => projectsApi.listVersions(projectId as number),
    enabled: projectId !== null,
  });
  const versions = [...(versionsQuery.data ?? [])].sort((a, b) => b.version - a.version);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const version = selectedVersion ?? versions[0]?.version ?? null;

  const versionDetailQuery = useQuery({
    queryKey: ["estimate-version", projectId, version],
    queryFn: () => projectsApi.getVersion(projectId as number, version as number),
    enabled: projectId !== null && version !== null,
  });

  function handleProjectChange(id: number) {
    setSelectedProjectId(id);
    setSelectedVersion(null);
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Reports</h1>
        <p className="text-sm text-muted-foreground">Generate a client-ready Excel workbook or PDF proposal for any saved estimate version.</p>
      </div>

      {projectsQuery.isLoading && <Skeleton className="h-24 w-full" />}

      {!projectsQuery.isLoading && projectsWithEstimates.length === 0 && (
        <EmptyState
          icon={BarChart3}
          title="Nothing to export yet"
          description="Create and save an estimate first."
          action={
            <Link href="/estimate/new" className={cn(buttonVariants({ size: "sm" }))}>
              New estimate
            </Link>
          }
        />
      )}

      {projectsWithEstimates.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Choose an estimate</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-end gap-4">
            <div className="flex min-w-48 flex-col gap-1.5">
              <Label htmlFor="report-project">Project</Label>
              <Select id="report-project" value={projectId ?? ""} onChange={(e) => handleProjectChange(Number(e.target.value))}>
                {projectsWithEstimates.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex min-w-32 flex-col gap-1.5">
              <Label htmlFor="report-version">Version</Label>
              <Select id="report-version" value={version ?? ""} onChange={(e) => setSelectedVersion(Number(e.target.value))}>
                {versions.map((v) => (
                  <option key={v.version} value={v.version}>
                    v{v.version} &middot; {formatDate(v.created_at)}
                  </option>
                ))}
              </Select>
            </div>
            {projectId !== null && version !== null && (
              <div className="ml-auto">
                <ExportButtons projectId={projectId} version={version} projectName={versionDetailQuery.data?.result.project_name ?? "estimate"} />
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {versionDetailQuery.isLoading && <Skeleton className="h-32 w-full" />}

      {versionDetailQuery.data && (
        <Card>
          <CardHeader>
            <CardTitle>{versionDetailQuery.data.result.project_name}</CardTitle>
            <CardDescription>
              v{versionDetailQuery.data.version} &middot; generated {formatDate(versionDetailQuery.data.created_at)}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <CostCard cost={versionDetailQuery.data.result.cost} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
