"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { FolderKanban, Receipt, ShieldAlert, TrendingUp, Users } from "lucide-react";
import Link from "next/link";

import { MetricCard } from "@/components/finops/metric-card";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { projectsApi } from "@/lib/api-client";
import { cn, formatDate } from "@/lib/utils";
import { useAuth } from "@/contexts/auth-context";
import { useCurrency } from "@/contexts/currency-context";

function AdminOverview() {
  const { formatMoney } = useCurrency();
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: projectsApi.list });
  const projects = projectsQuery.data ?? [];

  const versionQueries = useQueries({
    queries: projects
      .filter((p) => p.latest_version)
      .map((p) => ({
        queryKey: ["project-versions", p.id],
        queryFn: () => projectsApi.listVersions(p.id),
        staleTime: 30_000,
      })),
  });
  const isLoading = projectsQuery.isLoading || versionQueries.some((q) => q.isLoading);

  const rows = projects
    .filter((p) => p.latest_version)
    .map((p, i) => {
      const versions = versionQueries[i]?.data ?? [];
      const latest = versions.find((v) => v.version === p.latest_version) ?? versions.at(-1);
      return { project: p, latest, versionCount: versions.length };
    })
    .sort((a, b) => (b.latest?.total_monthly ?? 0) - (a.latest?.total_monthly ?? 0));

  const totalMonthly = rows.reduce((sum, r) => sum + (r.latest?.total_monthly ?? 0), 0);
  const totalVersions = rows.reduce((sum, r) => sum + r.versionCount, 0);
  const uniqueOwners = new Set(projects.map((p) => p.owner_id)).size;
  const currency = rows[0]?.latest?.currency ?? "USD";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Admin</h1>
        <p className="text-sm text-muted-foreground">Organization-wide visibility across every project - not just your own.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Total monthly spend" value={formatMoney(totalMonthly, currency)} icon={TrendingUp} isLoading={isLoading} />
        <MetricCard label="Total projects" value={String(projects.length)} icon={FolderKanban} isLoading={projectsQuery.isLoading} />
        <MetricCard label="Estimate versions" value={String(totalVersions)} icon={Receipt} isLoading={isLoading} />
        <MetricCard label="Distinct project owners" value={String(uniqueOwners)} icon={Users} isLoading={projectsQuery.isLoading} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All projects</CardTitle>
          <CardDescription>Sorted by latest monthly cost, highest first</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading && <Skeleton className="h-48 w-full" />}
          {!isLoading && rows.length === 0 && (
            <EmptyState icon={FolderKanban} title="No priced projects yet" />
          )}
          {!isLoading && rows.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Project</TableHead>
                  <TableHead>Owner</TableHead>
                  <TableHead>Versions</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="text-right">Latest monthly cost</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(({ project, latest, versionCount }) => (
                  <TableRow key={project.id}>
                    <TableCell className="font-medium text-foreground">
                      <Link href={`/projects/${project.id}`} className="hover:text-primary hover:underline">
                        {project.name}
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">User #{project.owner_id}</TableCell>
                    <TableCell>
                      <Badge variant="secondary">{versionCount}</Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{formatDate(project.updated_at)}</TableCell>
                    <TableCell className="text-right font-medium">{latest ? formatMoney(latest.total_monthly, latest.currency) : "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function AdminPage() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return <Skeleton className="h-48 w-full" />;
  }

  if (user?.role !== "admin") {
    return (
      <EmptyState
        icon={ShieldAlert}
        title="Admins only"
        description="This page is restricted to accounts with the admin role."
        action={
          <Link href="/dashboard" className={cn(buttonVariants({ size: "sm" }))}>
            Back to dashboard
          </Link>
        }
      />
    );
  }

  return <AdminOverview />;
}
