"use client";

import { Fragment, useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useCurrency } from "@/contexts/currency-context";
import type { ResourceCostSummary, ResourceStatus } from "@/lib/types";

function StatusBadge({ status }: { status: ResourceStatus }) {
  if (status === "unsupported") return <Badge variant="destructive"><XCircle />Unsupported</Badge>;
  if (status === "normalized") return <Badge variant="warning"><AlertTriangle />Normalized</Badge>;
  if (status === "assumption") return <Badge variant="warning"><AlertTriangle />Assumption</Badge>;
  return <Badge variant="success"><CheckCircle2 />Valid</Badge>;
}

/** "Why this price?" detail - region, SKU, pricing source, and (when the
 * platform substituted a value) the requested vs. normalized configuration
 * and the reason - sourced entirely from what the PricingProvider/
 * NormalizationEngine already computed, never invented here. */
function ResourceDetailRow({ r, colSpan }: { r: ResourceCostSummary; colSpan: number }) {
  return (
    <TableRow className="bg-muted/30 hover:bg-muted/30">
      <TableCell colSpan={colSpan} className="whitespace-normal py-3 text-sm">
        <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <dt className="text-xs text-muted-foreground">Region</dt>
            <dd className="text-foreground">{r.region ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">SKU</dt>
            <dd className="text-foreground">{r.sku_id ?? "(multiple SKUs)"}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Pricing source</dt>
            <dd className="text-foreground">{r.pricing_source ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Requested configuration</dt>
            <dd className="text-foreground">{r.requested_configuration ?? r.configuration}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Normalized configuration</dt>
            <dd className="text-foreground">{r.normalized_configuration ?? r.configuration}</dd>
          </div>
          {r.assumption_reason && (
            <div className="sm:col-span-2 lg:col-span-3">
              <dt className="text-xs text-muted-foreground">Assumption</dt>
              <dd className="text-foreground">{r.assumption_reason}</dd>
            </div>
          )}
        </dl>
      </TableCell>
    </TableRow>
  );
}

/** One row per distinct resource on the estimate - Compute Engine,
 * Persistent Disk, Cloud SQL, Networking, GKE, and every GCP service
 * catalog selection. Resources with the same configuration are already
 * merged (with quantities summed) by the backend
 * (app/catalog/{legacy_,}resource_summary.py), so each row here is
 * calculated independently: Resource | Configuration | Quantity | Unit
 * Cost | Subtotal | Status, ending in a grand total and a category-total
 * breakdown across every resource. Click a row to see why it costs what it
 * costs (region/SKU/pricing source/requested vs. normalized config). */
export function ResourceSummaryTable({
  resourceSummaries,
  categoryTotals,
}: {
  resourceSummaries: ResourceCostSummary[] | undefined | null;
  categoryTotals?: Record<string, number> | undefined | null;
}) {
  const { formatMoney } = useCurrency();
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const rows = resourceSummaries ?? [];
  if (rows.length === 0) return null;

  const grandTotal = rows.reduce((sum, r) => sum + r.subtotal, 0);
  const currency = rows[0].currency;
  const categories = Object.entries(categoryTotals ?? {});

  function toggle(i: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }

  return (
    <div className="flex flex-col gap-4" data-testid="resource-summary-table">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8" />
            <TableHead>Resource</TableHead>
            <TableHead>Configuration</TableHead>
            <TableHead>Quantity</TableHead>
            <TableHead>Unit cost</TableHead>
            <TableHead className="text-right">Subtotal</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r, i) => {
            const isOpen = expanded.has(i);
            return (
              <Fragment key={`${r.resource_name}-${r.configuration}-${i}`}>
                <TableRow
                  className="cursor-pointer"
                  onClick={() => toggle(i)}
                  aria-expanded={isOpen}
                >
                  <TableCell className="text-muted-foreground">
                    {isOpen ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                  </TableCell>
                  <TableCell className="font-medium text-foreground">
                    {r.resource_name}
                    {r.category && <span className="ml-1.5 text-xs text-muted-foreground"> ({r.category})</span>}
                  </TableCell>
                  <TableCell className="whitespace-normal text-muted-foreground">{r.configuration}</TableCell>
                  <TableCell className="text-muted-foreground">{r.quantity.toLocaleString()}</TableCell>
                  <TableCell className="text-muted-foreground">{formatMoney(r.unit_cost, r.currency)}</TableCell>
                  <TableCell className="text-right font-medium">{formatMoney(r.subtotal, r.currency)}</TableCell>
                  <TableCell>
                    <StatusBadge status={r.status} />
                  </TableCell>
                </TableRow>
                {isOpen && <ResourceDetailRow r={r} colSpan={7} />}
              </Fragment>
            );
          })}
        </TableBody>
        <TableFooter>
          <TableRow className="hover:bg-transparent">
            <TableCell colSpan={5} />
            <TableCell className="text-right text-base font-semibold text-foreground">
              {formatMoney(grandTotal, currency)}
            </TableCell>
            <TableCell />
          </TableRow>
          <TableRow className="hover:bg-transparent">
            <TableCell colSpan={5} className="text-base font-semibold text-foreground">
              Grand total (all resources)
            </TableCell>
            <TableCell colSpan={2} />
          </TableRow>
        </TableFooter>
      </Table>

      {categories.length > 0 && (
        <div className="flex flex-col gap-1.5 rounded-md border border-border p-3">
          <p className="text-xs font-medium text-muted-foreground">Category totals</p>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-3">
            {categories.map(([category, total]) => (
              <div key={category} className="flex items-center justify-between gap-2 text-sm">
                <span className="text-muted-foreground">{category}</span>
                <span className="font-medium text-foreground">{formatMoney(total, currency)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
