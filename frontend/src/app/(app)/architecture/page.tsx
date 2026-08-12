"use client";

import { useQuery } from "@tanstack/react-query";
import { Network } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ArchitecturePanel } from "@/components/architecture-panel";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { projectsApi } from "@/lib/api-client";
import { cn } from "@/lib/utils";

export default function ArchitecturePage() {
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: projectsApi.list });
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);

  const projectsWithEstimates = (projectsQuery.data ?? []).filter((p) => p.latest_version);
  // Derived rather than synced via effect: once the list loads, fall back
  // to the first project until the user explicitly picks one.
  const projectId = selectedProjectId ?? projectsWithEstimates[0]?.id ?? null;

  const versionsQuery = useQuery({
    queryKey: ["project-versions", projectId],
    queryFn: () => projectsApi.listVersions(projectId as number),
    enabled: projectId !== null,
  });
  const versions = [...(versionsQuery.data ?? [])].sort((a, b) => b.version - a.version);
  const version = selectedVersion ?? versions[0]?.version ?? null;

  const versionDetailQuery = useQuery({
    queryKey: ["estimate-version", projectId, version],
    queryFn: () => projectsApi.getVersion(projectId as number, version as number),
    enabled: projectId !== null && version !== null,
  });

  function handleProjectChange(id: number) {
    setSelectedProjectId(id);
    setSelectedVersion(null); // reset so the new project's latest version is picked
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Architecture</h1>
        <p className="text-sm text-muted-foreground">The recommended service architecture behind any saved estimate, with the reasoning for each choice.</p>
      </div>

      {projectsQuery.isLoading && <Skeleton className="h-24 w-full" />}

      {!projectsQuery.isLoading && projectsWithEstimates.length === 0 && (
        <EmptyState
          icon={Network}
          title="No priced estimates yet"
          description="Create an estimate first - its recommended architecture will show up here."
          action={
            <Link href="/estimate/new" className={cn(buttonVariants({ size: "sm" }))}>
              New estimate
            </Link>
          }
        />
      )}

      {projectsWithEstimates.length > 0 && (
        <Card>
          <CardContent className="flex flex-wrap gap-4 pt-5">
            <div className="flex min-w-48 flex-col gap-1.5">
              <Label htmlFor="project-picker">Project</Label>
              <Select id="project-picker" value={projectId ?? ""} onChange={(e) => handleProjectChange(Number(e.target.value))}>
                {projectsWithEstimates.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex min-w-32 flex-col gap-1.5">
              <Label htmlFor="version-picker">Version</Label>
              <Select id="version-picker" value={version ?? ""} onChange={(e) => setSelectedVersion(Number(e.target.value))}>
                {versions.map((v) => (
                  <option key={v.version} value={v.version}>
                    v{v.version}
                  </option>
                ))}
              </Select>
            </div>
          </CardContent>
        </Card>
      )}

      {versionDetailQuery.isLoading && <Skeleton className="h-96 w-full" />}

      {versionDetailQuery.data && (
        <Card>
          <CardHeader>
            <CardTitle>{versionDetailQuery.data.result.project_name}</CardTitle>
            <CardDescription>Region: {versionDetailQuery.data.result.normalized_spec.region} &middot; Strategy: {versionDetailQuery.data.result.strategy_used}</CardDescription>
          </CardHeader>
          <CardContent>
            <ArchitecturePanel architecture={versionDetailQuery.data.result.architecture} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
