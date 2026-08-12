import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCurrency } from "@/lib/utils";
import type { CostBreakdown } from "@/lib/types";

function SummaryCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-xs font-medium uppercase tracking-wide text-neutral-500">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold">{value}</p>
        {sub && <p className="mt-1 text-xs text-neutral-500">{sub}</p>}
      </CardContent>
    </Card>
  );
}

export function CostSummaryCards({ cost }: { cost: CostBreakdown }) {
  const totalDiscount = cost.discounts.reduce((sum, d) => sum + d.monthly_savings, 0);
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <SummaryCard label="Monthly" value={formatCurrency(cost.total_monthly, cost.currency)} />
      <SummaryCard label="Yearly" value={formatCurrency(cost.total_yearly, cost.currency)} />
      <SummaryCard label="3-Year" value={formatCurrency(cost.total_three_year, cost.currency)} />
      <SummaryCard
        label="Discounts applied"
        value={formatCurrency(totalDiscount, cost.currency)}
        sub={cost.discounts.map((d) => `${d.name} (${d.percent_off}%)`).join(", ") || "None"}
      />
    </div>
  );
}
