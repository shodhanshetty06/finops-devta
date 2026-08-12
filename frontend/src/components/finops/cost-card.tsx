"use client";

import { Calendar, CalendarClock, CalendarRange, TicketPercent } from "lucide-react";

import { MetricCard } from "@/components/finops/metric-card";
import { useCurrency } from "@/contexts/currency-context";
import type { CostBreakdown } from "@/lib/types";

/** The four headline numbers for any priced estimate - monthly/yearly/3yr
 * totals plus total discounts applied. Reused on the estimate result page,
 * the standalone New Estimate tool, and the Questionnaire wizard. Displayed
 * in the user's chosen currency (see CurrencyProvider) - the estimate is
 * still priced and stored in cost.currency (USD) underneath. */
export function CostCard({ cost }: { cost: CostBreakdown }) {
  const { formatMoney } = useCurrency();
  const totalDiscount = cost.discounts.reduce((sum, d) => sum + d.monthly_savings, 0);
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <MetricCard label="Monthly" value={formatMoney(cost.total_monthly, cost.currency)} icon={Calendar} />
      <MetricCard label="Yearly" value={formatMoney(cost.total_yearly, cost.currency)} icon={CalendarClock} />
      <MetricCard label="3-Year" value={formatMoney(cost.total_three_year, cost.currency)} icon={CalendarRange} />
      <MetricCard
        label="Discounts applied"
        value={formatMoney(totalDiscount, cost.currency)}
        icon={TicketPercent}
        hint={cost.discounts.length > 0 ? cost.discounts.map((d) => `${d.name} (${d.percent_off}%)`).join(", ") : "None applied"}
      />
    </div>
  );
}
