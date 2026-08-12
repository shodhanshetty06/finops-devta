"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useCurrency } from "@/contexts/currency-context";
import type { CostBreakdown } from "@/lib/types";

export function CostProjectionChart({ cost }: { cost: CostBreakdown }) {
  const { formatMoney } = useCurrency();
  const data = [
    { period: "Monthly", amount: cost.total_monthly },
    { period: "Yearly", amount: cost.total_yearly },
    { period: "3-Year", amount: cost.total_three_year },
  ];
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
          <XAxis dataKey="period" tick={{ fontSize: 12, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
          <YAxis
            tick={{ fontSize: 12, fill: "var(--color-muted-foreground)" }}
            tickFormatter={(v: number) => formatMoney(v, cost.currency)}
            width={90}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            formatter={(value: unknown) => formatMoney(Number(value), cost.currency)}
            cursor={{ fill: "var(--color-muted)" }}
            contentStyle={{ background: "var(--color-surface-raised)", border: "1px solid var(--color-border)", borderRadius: 8, fontSize: 13 }}
          />
          <Bar dataKey="amount" fill="var(--color-primary)" radius={[4, 4, 0, 0]} maxBarSize={64} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
