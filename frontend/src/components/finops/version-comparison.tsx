"use client";

import { useState } from "react";
import { GitCompare } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/finops/field";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useCurrency } from "@/contexts/currency-context";
import { apiErrorMessage, projectsApi } from "@/lib/api-client";
import type { EstimateVersionSummary, VersionComparison as VersionComparisonType } from "@/lib/types";

function DeltaText({ value, currency, formatMoney }: { value: number; currency: string; formatMoney: (v: number, c: string) => string }) {
  const sign = value > 0 ? "+" : "";
  const tone = value > 0 ? "text-error-600 dark:text-error-400" : value < 0 ? "text-success-700 dark:text-success-300" : "text-muted-foreground";
  return <span className={`font-medium ${tone}`}>{sign}{formatMoney(value, currency)}</span>;
}

/** Exposes the existing `GET /projects/{id}/estimates/compare` endpoint
 * (backend/app/api/routers/projects.py) - diffs two already-saved versions'
 * totals and per-category costs. No new comparison logic here, this is UI
 * over an endpoint that already existed and worked. */
export function VersionComparisonCard({ projectId, versions }: { projectId: number; versions: EstimateVersionSummary[] }) {
  const { formatMoney } = useCurrency();
  const sorted = [...versions].sort((a, b) => b.version - a.version);
  const [fromVersion, setFromVersion] = useState<number | null>(sorted[1]?.version ?? null);
  const [toVersion, setToVersion] = useState<number | null>(sorted[0]?.version ?? null);
  const [loading, setLoading] = useState(false);
  const [comparison, setComparison] = useState<VersionComparisonType | null>(null);

  if (sorted.length < 2) return null;

  async function compare() {
    if (fromVersion === null || toVersion === null || fromVersion === toVersion) return;
    setLoading(true);
    try {
      setComparison(await projectsApi.compareVersions(projectId, fromVersion, toVersion));
    } catch (err) {
      toast.error("Could not compare these versions", { description: apiErrorMessage(err) });
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <GitCompare className="size-4" />
          Compare versions
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="From" htmlFor="from-version">
            <Select id="from-version" value={fromVersion ?? ""} onChange={(e) => setFromVersion(Number(e.target.value))}>
              {sorted.map((v) => (
                <option key={v.version} value={v.version}>
                  v{v.version} - {formatMoney(v.total_monthly, v.currency)}/mo
                </option>
              ))}
            </Select>
          </Field>
          <Field label="To" htmlFor="to-version">
            <Select id="to-version" value={toVersion ?? ""} onChange={(e) => setToVersion(Number(e.target.value))}>
              {sorted.map((v) => (
                <option key={v.version} value={v.version}>
                  v{v.version} - {formatMoney(v.total_monthly, v.currency)}/mo
                </option>
              ))}
            </Select>
          </Field>
          <Button size="sm" onClick={compare} disabled={loading || fromVersion === toVersion}>
            {loading && <Spinner />}
            Compare
          </Button>
        </div>
        {fromVersion === toVersion && <p className="text-xs text-muted-foreground">Pick two different versions.</p>}

        {comparison && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <span>
                v{comparison.from_version}: <span className="font-medium text-foreground">{formatMoney(comparison.from_total_monthly, comparison.currency)}</span>
              </span>
              <span>→</span>
              <span>
                v{comparison.to_version}: <span className="font-medium text-foreground">{formatMoney(comparison.to_total_monthly, comparison.currency)}</span>
              </span>
              <span>
                Difference: <DeltaText value={comparison.delta_monthly} currency={comparison.currency} formatMoney={formatMoney} />{" "}
                ({comparison.delta_percent > 0 ? "+" : ""}{comparison.delta_percent.toFixed(1)}%)
              </span>
            </div>
            {Object.keys(comparison.category_deltas).length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Category</TableHead>
                    <TableHead className="text-right">Change</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(comparison.category_deltas).map(([category, delta]) => (
                    <TableRow key={category}>
                      <TableCell>{category}</TableCell>
                      <TableCell className="text-right">
                        <DeltaText value={delta} currency={comparison.currency} formatMoney={formatMoney} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
