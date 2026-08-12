"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3, FileUp, History as HistoryIcon, ListPlus, Plus, Receipt } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { MetricCard } from "@/components/finops/metric-card";
import { Timeline, type TimelineItem } from "@/components/finops/timeline";
import { VersionComparisonCard } from "@/components/finops/version-comparison";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { apiErrorMessage, projectsApi } from "@/lib/api-client";
import { cn, formatDate } from "@/lib/utils";
import { useCurrency } from "@/contexts/currency-context";

function ProjectDetail({ projectId }: { projectId: number }) {
  const { formatMoney } = useCurrency();
  const projectQuery = useQuery({ queryKey: ["project", projectId], queryFn: () => projectsApi.get(projectId) });
  const versionsQuery = useQuery({
    queryKey: ["project-versions", projectId],
    queryFn: () => projectsApi.listVersions(projectId),
  });

  if (projectQuery.isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (projectQuery.isError || !projectQuery.data) {
    return (
      <EmptyState
        icon={FileUp}
        title="Couldn't load this project"
        description={apiErrorMessage(projectQuery.error)}
      />
    );
  }

  const project = projectQuery.data;
  const versions = [...(versionsQuery.data ?? [])].sort((a, b) => b.version - a.version);
  const latest = versions[0];
  const currency = latest?.currency ?? "USD";
  const avgMonthly = versions.length > 0 ? versions.reduce((sum, v) => sum + v.total_monthly, 0) / versions.length : 0;

  const timelineItems: TimelineItem[] = versions.map((v, i) => ({
    id: v.version,
    title: (
      <span className="flex items-center gap-2">
        <Badge variant={i === 0 ? "default" : "secondary"}>v{v.version}</Badge>
        {i === 0 && <span className="text-xs font-medium text-primary">Latest</span>}
      </span>
    ),
    description: formatMoney(v.total_monthly, v.currency) + "/mo",
    timestamp: formatDate(v.created_at),
    tone: i === 0 ? "primary" : "default",
    href: `/projects/${projectId}/estimates/${v.version}`,
  }));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">{project.name}</h1>
          <p className="text-xs text-muted-foreground">Created {formatDate(project.created_at)}</p>
        </div>
        <div className="flex gap-2">
          <Link href={`/projects/${projectId}/intake`} className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
            <FileUp className="h-4 w-4" />
            Upload / extract
          </Link>
          {versions.length > 0 && (
            <Link href={`/estimate/existing?project=${projectId}`} className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
              <ListPlus className="h-4 w-4" />
              Add to estimate
            </Link>
          )}
          <Link href={`/projects/${projectId}/new`} className={cn(buttonVariants({ size: "sm" }))}>
            <Plus className="h-4 w-4" />
            New estimate
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <MetricCard label="Latest monthly cost" value={latest ? formatMoney(latest.total_monthly, currency) : "—"} icon={Receipt} />
        <MetricCard label="Estimate versions" value={String(versions.length)} icon={HistoryIcon} />
        <MetricCard label="Avg. monthly across versions" value={versions.length > 0 ? formatMoney(avgMonthly, currency) : "—"} icon={BarChart3} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Estimate history</CardTitle>
          <CardDescription>Every version of this project&apos;s estimate, most recent first</CardDescription>
        </CardHeader>
        <CardContent>
          {versionsQuery.isLoading && (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          )}
          {!versionsQuery.isLoading && versions.length === 0 && (
            <EmptyState
              icon={Receipt}
              title="No estimates yet"
              description="Build one from scratch or upload a filled questionnaire."
              action={
                <Link href={`/projects/${projectId}/new`} className={cn(buttonVariants({ size: "sm" }))}>
                  <Plus className="h-4 w-4" />
                  New estimate
                </Link>
              }
            />
          )}
          {!versionsQuery.isLoading && versions.length > 0 && <Timeline items={timelineItems} />}
        </CardContent>
      </Card>

      {versions.length > 1 && <VersionComparisonCard projectId={projectId} versions={versions} />}

      {latest && (
        <Card>
          <CardHeader>
            <CardTitle>Reports</CardTitle>
            <CardDescription>Export the latest version as a client-ready document</CardDescription>
          </CardHeader>
          <CardContent>
            <Link
              href={`/projects/${projectId}/estimates/${latest.version}`}
              className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
            >
              Open v{latest.version} to export
            </Link>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  return <ProjectDetail projectId={Number(params.id)} />;
}
