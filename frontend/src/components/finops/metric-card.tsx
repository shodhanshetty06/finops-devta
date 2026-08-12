import type { LucideIcon } from "lucide-react";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export interface MetricCardProps {
  label: string;
  value: string;
  icon?: LucideIcon;
  /** Positive = good/green, negative = attention/amber - direction is
   * caller-decided (e.g. a cost increase is "negative" even though the
   * number itself is positive). */
  trend?: { value: string; direction: "up" | "down"; tone?: "positive" | "negative" };
  hint?: string;
  isLoading?: boolean;
  className?: string;
}

export function MetricCard({ label, value, icon: Icon, trend, hint, isLoading, className }: MetricCardProps) {
  if (isLoading) {
    return (
      <Card className={cn("p-5", className)}>
        <Skeleton className="h-3.5 w-24" />
        <Skeleton className="mt-3 h-7 w-32" />
        <Skeleton className="mt-3 h-3 w-20" />
      </Card>
    );
  }

  const TrendIcon = trend?.direction === "up" ? ArrowUpRight : ArrowDownRight;
  const trendTone = trend?.tone ?? (trend?.direction === "up" ? "positive" : "negative");

  return (
    <Card className={cn("flex flex-col gap-3 p-5", className)}>
      <div className="flex items-center justify-between">
        <p className="text-[13px] font-medium text-muted-foreground">{label}</p>
        {Icon && (
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-accent text-accent-foreground">
            <Icon className="h-4 w-4" />
          </span>
        )}
      </div>
      <p className="text-[26px] font-semibold leading-none tracking-tight text-foreground">{value}</p>
      {(trend || hint) && (
        <div className="flex items-center gap-1.5 text-xs">
          {trend && (
            <span
              className={cn(
                "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 font-medium",
                trendTone === "positive"
                  ? "bg-success-50 text-success-700 dark:bg-success-900/30 dark:text-success-300"
                  : "bg-error-50 text-error-700 dark:bg-error-900/30 dark:text-error-300",
              )}
            >
              <TrendIcon className="h-3 w-3" />
              {trend.value}
            </span>
          )}
          {hint && <span className="text-muted-foreground">{hint}</span>}
        </div>
      )}
    </Card>
  );
}
