"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { History as HistoryIcon } from "lucide-react";
import Link from "next/link";

import { Timeline, type TimelineItem } from "@/components/finops/timeline";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { projectsApi } from "@/lib/api-client";
import { cn, formatDate } from "@/lib/utils";
import { useCurrency } from "@/contexts/currency-context";

export default function HistoryPage() {
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

  const items: TimelineItem[] = projects
    .filter((p) => p.latest_version)
    .flatMap((p, i) =>
      (versionQueries[i]?.data ?? []).map((v) => ({
        id: `${p.id}-${v.version}`,
        title: (
          <span className="flex items-center gap-2">
            <span className="font-medium text-foreground">{p.name}</span>
            <Badge variant="secondary">v{v.version}</Badge>
          </span>
        ),
        description: formatMoney(v.total_monthly, v.currency) + "/mo",
        timestamp: formatDate(v.created_at),
        href: `/projects/${p.id}/estimates/${v.version}`,
        sortKey: new Date(v.created_at).getTime(),
        tone: "primary" as const,
      })),
    )
    .sort((a, b) => b.sortKey - a.sortKey);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">History</h1>
        <p className="text-sm text-muted-foreground">Every estimate version across every project, most recent first.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Activity</CardTitle>
          <CardDescription>{items.length} estimate version{items.length === 1 ? "" : "s"} total</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <div className="flex flex-col gap-3">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          )}
          {!isLoading && items.length === 0 && (
            <EmptyState
              icon={HistoryIcon}
              title="Nothing here yet"
              description="Create your first estimate to start building history."
              action={
                <Link href="/estimate/new" className={cn(buttonVariants({ size: "sm" }))}>
                  New estimate
                </Link>
              }
            />
          )}
          {!isLoading && items.length > 0 && <Timeline items={items} />}
        </CardContent>
      </Card>
    </div>
  );
}
