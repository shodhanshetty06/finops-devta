"use client";

import { ArchitecturePanel } from "@/components/architecture-panel";
import { AssumptionsList } from "@/components/assumptions-list";
import { CostBreakdownChart } from "@/components/cost-breakdown-chart";
import { CostCard } from "@/components/finops/cost-card";
import { CostProjectionChart } from "@/components/cost-projection-chart";
import { ValidationTable } from "@/components/finops/validation-table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PricingTable } from "@/components/finops/pricing-table";
import { ResourceSummaryTable } from "@/components/finops/resource-summary-table";
import { useAuth } from "@/contexts/auth-context";
import { formatDate } from "@/lib/utils";
import type { EstimateResult } from "@/lib/types";

/** Renders the full body of a priced estimate - cost, charts, line items,
 * architecture, validation, assumptions, and (admins only) audit log.
 * Shared by the saved-version page (projects/[id]/estimates/[version]) and
 * the standalone estimate tools (New Estimate, Questionnaire) so the same
 * result always looks the same regardless of how it was produced. */
export function EstimateResultView({ result }: { result: EstimateResult }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  return (
    <div className="flex flex-col gap-6">
      <CostCard cost={result.cost} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Cost breakdown by category</CardTitle>
          </CardHeader>
          <CardContent>
            <CostBreakdownChart lineItems={result.cost.line_items} currency={result.cost.currency} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Cost projection</CardTitle>
          </CardHeader>
          <CardContent>
            <CostProjectionChart cost={result.cost} />
          </CardContent>
        </Card>
      </div>

      {(result.cost.resource_summaries?.length ?? 0) > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Selected resources</CardTitle>
          </CardHeader>
          <CardContent>
            <ResourceSummaryTable resourceSummaries={result.cost.resource_summaries} categoryTotals={result.cost.category_totals} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Line items</CardTitle>
        </CardHeader>
        <CardContent>
          <PricingTable cost={result.cost} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recommended architecture</CardTitle>
        </CardHeader>
        <CardContent>
          <ArchitecturePanel architecture={result.architecture} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Validation &amp; assumptions
            {result.validation.results.length + result.assumptions.length > 0 && (
              <Badge variant="secondary">{result.validation.results.length + result.assumptions.length}</Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="validation">
            <TabsList>
              <TabsTrigger value="validation">Validation ({result.validation.results.length})</TabsTrigger>
              <TabsTrigger value="assumptions">Assumptions ({result.assumptions.length})</TabsTrigger>
            </TabsList>
            <TabsContent value="validation">
              <ValidationTable report={result.validation} />
            </TabsContent>
            <TabsContent value="assumptions">
              <AssumptionsList assumptions={result.assumptions} />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {isAdmin && (
        <Card>
          <CardHeader>
            <CardTitle>Audit log</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-1.5 text-xs text-muted-foreground">
              {result.audit_log.entries.map((e, i) => (
                <li key={i} className="flex flex-wrap gap-1.5">
                  <span className="font-mono">{formatDate(e.timestamp)}</span>
                  <span>&middot;</span>
                  <span className="font-medium text-foreground">{e.actor}</span>
                  <span>&middot;</span>
                  <span>{e.action}</span>
                  {e.details && <span>&mdash; {e.details}</span>}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
