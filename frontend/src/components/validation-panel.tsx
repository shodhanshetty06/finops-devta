"use client";

import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import type { ValidationReport, ValidationResult } from "@/lib/types";

function SeverityIcon({ severity }: { severity: ValidationResult["severity"] }) {
  if (severity === "blocker") return <XCircle className="h-4 w-4 shrink-0" />;
  if (severity === "warning") return <AlertTriangle className="h-4 w-4 shrink-0" />;
  return <Info className="h-4 w-4 shrink-0" />;
}

function severityClasses(severity: ValidationResult["severity"]): string {
  switch (severity) {
    case "blocker":
      return "text-error-700 bg-error-50 border-error-200 dark:text-error-300 dark:bg-error-900/20 dark:border-error-900";
    case "warning":
      return "text-warning-700 bg-warning-50 border-warning-200 dark:text-warning-300 dark:bg-warning-900/20 dark:border-warning-900";
    default:
      return "text-primary-700 bg-primary-50 border-primary-200 dark:text-primary-300 dark:bg-primary-950 dark:border-primary-900";
  }
}

/** Compact, card-embedded validation summary - used inside wizards for
 * live "as you type" feedback. See finops/validation-table.tsx for the
 * full tabular version used on the Validation page and estimate results. */
export function ValidationPanel({ report, isLoading }: { report: ValidationReport | null; isLoading?: boolean }) {
  if (isLoading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner className="h-3.5 w-3.5" />
        Checking against supported Google Cloud configurations...
      </p>
    );
  }
  if (!report || report.results.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-success-200 bg-success-50 px-3 py-2 text-sm text-success-800 dark:border-success-900 dark:bg-success-900/20 dark:text-success-300">
        <CheckCircle2 className="h-4 w-4" />
        No issues found.
      </div>
    );
  }

  const blockers = report.results.filter((r) => r.severity === "blocker");
  const warnings = report.results.filter((r) => r.severity === "warning");
  const infos = report.results.filter((r) => r.severity === "info");
  const ordered = [...blockers, ...warnings, ...infos];

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        {blockers.length > 0 && <Badge variant="destructive">{blockers.length} blocker{blockers.length === 1 ? "" : "s"}</Badge>}
        {warnings.length > 0 && <Badge variant="warning">{warnings.length} warning{warnings.length === 1 ? "" : "s"}</Badge>}
        {infos.length > 0 && <Badge variant="secondary">{infos.length} note{infos.length === 1 ? "" : "s"}</Badge>}
      </div>
      <ul className="flex flex-col gap-2">
        {ordered.map((result, i) => (
          <li
            key={`${result.field}-${result.rule}-${i}`}
            className={cn("flex items-start gap-2 rounded-md border px-3 py-2 text-sm", severityClasses(result.severity))}
          >
            <SeverityIcon severity={result.severity} />
            <div className="flex flex-col gap-0.5">
              <span className="font-medium">{result.field}</span>
              <span>{result.reason}</span>
              {result.recommendation && <span className="text-xs opacity-80">{result.recommendation}</span>}
              {result.supported_value && result.supported_value !== result.requested_value && (
                <span className="text-xs opacity-80">
                  Requested {result.requested_value} &rarr; supported {result.supported_value}
                </span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
