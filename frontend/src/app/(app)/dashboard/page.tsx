"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from "recharts";
import {
  AlertTriangle,
  Boxes,
  CalendarRange,
  FilePlus2,
  FileSpreadsheet,
  FolderKanban,
  Lightbulb,
  PlusCircle,
  Receipt,
  Sparkles,
  TrendingUp,
  Upload,
} from "lucide-react";
import Link from "next/link";

import { ErrorBoundary } from "@/components/error-boundary";
import { MetricCard } from "@/components/finops/metric-card";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { optimizationApi, projectsApi } from "@/lib/api-client";
import { cn, formatDate } from "@/lib/utils";
import { useAuth } from "@/contexts/auth-context";
import { useCurrency } from "@/contexts/currency-context";

const QUICK_ACTIONS = [
  { label: "New Estimate", description: "Price a configuration in seconds", href: "/estimate/new", icon: PlusCircle },
  { label: "Existing Estimate", description: "Add or update services on a saved estimate", href: "/estimate/existing", icon: FilePlus2 },
  { label: "Upload Excel", description: "Import a filled questionnaire", href: "/upload", icon: Upload },
  { label: "Questionnaire", description: "Guided step-by-step intake", href: "/questionnaire", icon: FileSpreadsheet },
  { label: "All Projects", description: "Browse every project", href: "/projects", icon: FolderKanban },
];

function DashboardContent() {
  const { user } = useAuth();
  const { formatMoney } = useCurrency();
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: projectsApi.list });
  const projects = projectsQuery.data ?? [];

  const versionQueries = useQueries({
    queries: projects
      .filter((p) => p.latest_version)
      .map((p) => ({
        queryKey: ["project-versions", p.id],
        queryFn: () => projectsApi.listVersions(p.id),
        enabled: !!p.latest_version,
        staleTime: 30_000,
      })),
  });

  const isLoadingSpend = projectsQuery.isLoading || versionQueries.some((q) => q.isLoading);

  // Full latest-version detail (resource_summaries, assumptions,
  // category_totals) per project with a priced estimate - reuses the same
  // GET already used on the estimate version page, just fanned out across
  // every project instead of one, so the dashboard can surface FinOps
  // insights (not just raw totals) without any new backend endpoint.
  const projectsWithEstimates = projects.filter((p) => p.latest_version);
  const detailQueries = useQueries({
    queries: projectsWithEstimates.map((p) => ({
      queryKey: ["project-version-detail", p.id, p.latest_version],
      queryFn: () => projectsApi.getVersion(p.id, p.latest_version as number),
      staleTime: 30_000,
    })),
  });
  const isLoadingDetail = detailQueries.some((q) => q.isLoading);

  // Committed-Use-Discount opportunity for each priced project, assuming a
  // steady workload (the same CommitmentEngine every optimization panel
  // reuses) - "optimization opportunity" is real savings the estimate isn't
  // already capturing, not a fabricated figure.
  const commitmentQueries = useQueries({
    queries: detailQueries.map((q) => ({
      queryKey: ["dashboard-commitment", q.data?.estimate_id],
      queryFn: () => optimizationApi.commitmentRecommendation(q.data!.request, "steady", true),
      enabled: !!q.data,
      staleTime: 30_000,
    })),
  });

  const resourceCount = detailQueries.reduce((sum, q) => sum + (q.data?.result.cost.resource_summaries.length ?? 0), 0);
  const assumptionCount = detailQueries.reduce((sum, q) => sum + (q.data?.result.assumptions.length ?? 0), 0);
  const normalizedCount = detailQueries.reduce(
    (sum, q) => sum + (q.data?.result.cost.resource_summaries.filter((r) => r.status !== "valid").length ?? 0),
    0,
  );
  const categoryTotals = detailQueries.reduce<Record<string, number>>((acc, q) => {
    for (const [category, total] of Object.entries(q.data?.result.cost.category_totals ?? {})) {
      acc[category] = (acc[category] ?? 0) + total;
    }
    return acc;
  }, {});
  const optimizationOpportunity = commitmentQueries.reduce((sum, q) => {
    const rec = q.data;
    if (!rec || rec.recommended_term_years === 0) return sum;
    const option = rec.options.find((o) => o.term_years === rec.recommended_term_years);
    return sum + (option?.monthly_savings_vs_on_demand ?? 0);
  }, 0);

  const chartData = projects
    .filter((p) => p.latest_version)
    .map((p, i) => {
      const versions = versionQueries[i]?.data ?? [];
      const latest = versions.find((v) => v.version === p.latest_version) ?? versions.at(-1);
      return { name: p.name.length > 14 ? `${p.name.slice(0, 14)}…` : p.name, monthly: latest?.total_monthly ?? 0, currency: latest?.currency ?? "USD" };
    })
    .filter((d) => d.monthly > 0)
    .sort((a, b) => b.monthly - a.monthly)
    .slice(0, 8);

  const totalMonthly = chartData.reduce((sum, d) => sum + d.monthly, 0);
  const totalEstimates = versionQueries.reduce((sum, q) => sum + (q.data?.length ?? 0), 0);
  const activeProjects = projects.length;
  const avgPerProject = activeProjects > 0 ? totalMonthly / chartData.length || 0 : 0;
  const currency = chartData[0]?.currency ?? "USD";

  const recentProjects = [...projects]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 6);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">Welcome back{user ? `, ${user.full_name.split(" ")[0]}` : ""}</h1>
          <p className="text-sm text-muted-foreground">Here&apos;s what&apos;s happening across your Google Cloud estimates.</p>
        </div>
        <Link href="/estimate/new" className={cn(buttonVariants())}>
          <PlusCircle className="h-4 w-4" />
          New estimate
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Total monthly spend"
          value={formatMoney(totalMonthly, currency)}
          icon={TrendingUp}
          hint="Across latest versions"
          isLoading={isLoadingSpend}
        />
        <MetricCard label="Active projects" value={String(activeProjects)} icon={FolderKanban} isLoading={projectsQuery.isLoading} />
        <MetricCard label="Estimate versions" value={String(totalEstimates)} icon={Receipt} isLoading={isLoadingSpend} />
        <MetricCard
          label="Avg. monthly / project"
          value={formatMoney(avgPerProject, currency)}
          icon={FileSpreadsheet}
          isLoading={isLoadingSpend}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Annual cost"
          value={formatMoney(totalMonthly * 12, currency)}
          icon={CalendarRange}
          hint="Latest versions, x12"
          isLoading={isLoadingSpend}
        />
        <MetricCard label="Resources" value={String(resourceCount)} icon={Boxes} hint="Across latest versions" isLoading={isLoadingDetail} />
        <MetricCard
          label="Assumptions / normalized"
          value={`${assumptionCount} / ${normalizedCount}`}
          icon={AlertTriangle}
          hint="Substitutions made while pricing"
          isLoading={isLoadingDetail}
        />
        <MetricCard
          label="Optimization opportunity"
          value={optimizationOpportunity > 0 ? formatMoney(optimizationOpportunity, currency) : "—"}
          icon={Lightbulb}
          hint="Committed Use Discount, steady workload"
          isLoading={isLoadingDetail}
        />
      </div>

      {Object.keys(categoryTotals).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="size-4" />
              Cost by category
            </CardTitle>
            <CardDescription>Summed across every project&apos;s latest priced version</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 lg:grid-cols-5">
              {Object.entries(categoryTotals)
                .sort(([, a], [, b]) => b - a)
                .map(([category, total]) => (
                  <div key={category} className="flex flex-col gap-0.5">
                    <span className="text-xs text-muted-foreground">{category}</span>
                    <span className="text-sm font-semibold text-foreground">{formatMoney(total, currency)}</span>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Monthly cost by project</CardTitle>
            <CardDescription>Latest priced estimate version for each project</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoadingSpend ? (
              <Skeleton className="h-64 w-full" />
            ) : chartData.length === 0 ? (
              <EmptyState
                icon={TrendingUp}
                title="No priced estimates yet"
                description="Create your first estimate to see cost trends here."
                action={
                  <Link href="/estimate/new" className={cn(buttonVariants({ size: "sm" }))}>
                    New estimate
                  </Link>
                }
              />
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={chartData} margin={{ left: 0, right: 8, top: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 12, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 12, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} width={56} />
                  <RechartsTooltip
                    cursor={{ fill: "var(--color-muted)" }}
                    contentStyle={{ background: "var(--color-surface-raised)", border: "1px solid var(--color-border)", borderRadius: 8, fontSize: 13 }}
                    formatter={(value: unknown) => formatMoney(Number(value), currency)}
                  />
                  <Bar dataKey="monthly" fill="var(--color-primary)" radius={[4, 4, 0, 0]} maxBarSize={40} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quick actions</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            {QUICK_ACTIONS.map((action) => (
              <Link
                key={action.href}
                href={action.href}
                className="flex items-center gap-3 rounded-lg border border-transparent p-2.5 transition-colors hover:border-border hover:bg-muted/60"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-accent text-accent-foreground">
                  <action.icon className="h-4 w-4" />
                </span>
                <span className="flex flex-col">
                  <span className="text-sm font-medium text-foreground">{action.label}</span>
                  <span className="text-xs text-muted-foreground">{action.description}</span>
                </span>
              </Link>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle>Recent projects</CardTitle>
            <CardDescription>Most recently updated</CardDescription>
          </div>
          <Link href="/projects" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
            View all
          </Link>
        </CardHeader>
        <CardContent>
          {projectsQuery.isLoading ? (
            <div className="flex flex-col gap-2">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : recentProjects.length === 0 ? (
            <EmptyState
              icon={FolderKanban}
              title="No projects yet"
              description="Create your first project to start tracking versioned estimates."
              action={
                <Link href="/projects" className={cn(buttonVariants({ size: "sm" }))}>
                  Create a project
                </Link>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Project</TableHead>
                  <TableHead>Latest version</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="text-right">Open</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentProjects.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium text-foreground">{p.name}</TableCell>
                    <TableCell>
                      {p.latest_version ? <Badge>v{p.latest_version}</Badge> : <Badge variant="secondary">No estimates</Badge>}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{formatDate(p.updated_at)}</TableCell>
                    <TableCell className="text-right">
                      <Link href={`/projects/${p.id}`} className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}>
                        View
                      </Link>
                    </TableCell>
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

export default function DashboardPage() {
  return (
    <ErrorBoundary fallbackTitle="Couldn't load the dashboard">
      <DashboardContent />
    </ErrorBoundary>
  );
}
