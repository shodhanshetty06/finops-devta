import type { LucideIcon } from "lucide-react";

import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

/** Compact stat block - smaller and denser than MetricCard, meant for
 * grouping several side by side inside another card (e.g. a project's
 * budget usage, or catalog counts on the Pricing page) rather than as a
 * page-level KPI. */
export function StatCard({
  label,
  value,
  icon: Icon,
  progress,
  progressTone = "primary",
  className,
}: {
  label: string;
  value: string;
  icon?: LucideIcon;
  progress?: number;
  progressTone?: "primary" | "warning" | "error";
  className?: string;
}) {
  const toneClass = {
    primary: "bg-primary",
    warning: "bg-warning",
    error: "bg-destructive",
  }[progressTone];

  return (
    <div className={cn("flex flex-col gap-2 rounded-lg border border-border bg-surface p-4", className)}>
      <div className="flex items-center gap-2">
        {Icon && <Icon className="h-3.5 w-3.5 text-muted-foreground" />}
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
      </div>
      <p className="text-lg font-semibold text-foreground">{value}</p>
      {progress !== undefined && <Progress value={progress} indicatorClassName={toneClass} />}
    </div>
  );
}
