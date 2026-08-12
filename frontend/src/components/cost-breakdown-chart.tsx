"use client";

import { PieChart as PieChartIcon } from "lucide-react";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { EmptyState } from "@/components/ui/empty-state";
import { useCurrency } from "@/contexts/currency-context";
import type { CostLineItem } from "@/lib/types";

// A muted, professional categorical palette (Google Blue anchored, desaturated
// secondary hues) rather than a bright rainbow - keeps a multi-category chart
// readable without breaking the "no rainbow colors" design guidance.
const COLORS = ["#1a73e8", "#34a853", "#f9ab00", "#9334e6", "#0891b2", "#e8710a", "#5f6368", "#c5221f"];

export function CostBreakdownChart({ lineItems, currency }: { lineItems: CostLineItem[]; currency: string }) {
  const { formatMoney } = useCurrency();
  const byCategory = new Map<string, number>();
  for (const item of lineItems) {
    byCategory.set(item.category, (byCategory.get(item.category) ?? 0) + item.monthly_amount);
  }
  const data = Array.from(byCategory.entries()).map(([name, value]) => ({ name, value }));

  if (data.length === 0) {
    return <EmptyState icon={PieChartIcon} title="No priced line items" />;
  }

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={(d) => d.name}>
            {data.map((entry, i) => (
              <Cell key={entry.name} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value: unknown) => formatMoney(Number(value), currency)}
            contentStyle={{ background: "var(--color-surface-raised)", border: "1px solid var(--color-border)", borderRadius: 8, fontSize: 13 }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
