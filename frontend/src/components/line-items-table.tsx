import { Badge } from "@/components/ui/badge";
import { formatCurrency } from "@/lib/utils";
import type { CostBreakdown } from "@/lib/types";

export function LineItemsTable({ cost }: { cost: CostBreakdown }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-neutral-200 text-xs uppercase tracking-wide text-neutral-500 dark:border-neutral-800">
            <th className="py-2 pr-4">Category</th>
            <th className="py-2 pr-4">Description</th>
            <th className="py-2 pr-4">Quantity</th>
            <th className="py-2 pr-4">Unit price</th>
            <th className="py-2 pr-4 text-right">Monthly</th>
          </tr>
        </thead>
        <tbody>
          {cost.line_items.map((item, i) => (
            <tr key={`${item.sku_id ?? item.description}-${i}`} className="border-b border-neutral-100 dark:border-neutral-900">
              <td className="py-2 pr-4">
                <Badge variant="secondary">{item.category}</Badge>
              </td>
              <td className="py-2 pr-4">{item.description}</td>
              <td className="py-2 pr-4 whitespace-nowrap text-neutral-500">
                {item.quantity.toLocaleString()} {item.unit}
              </td>
              <td className="py-2 pr-4 whitespace-nowrap text-neutral-500">
                {formatCurrency(item.unit_price, item.currency)}/{item.unit}
              </td>
              <td className="py-2 pr-4 text-right font-medium">{formatCurrency(item.monthly_amount, item.currency)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t border-neutral-200 text-sm dark:border-neutral-800">
            <td colSpan={4} className="py-2 pr-4 text-neutral-500">Subtotal</td>
            <td className="py-2 pr-4 text-right">{formatCurrency(cost.subtotal_monthly, cost.currency)}</td>
          </tr>
          {cost.discounts.map((d) => (
            <tr key={d.name} className="text-sm text-green-700 dark:text-green-400">
              <td colSpan={4} className="py-1 pr-4">{d.name} ({d.percent_off}%)</td>
              <td className="py-1 pr-4 text-right">-{formatCurrency(d.monthly_savings, cost.currency)}</td>
            </tr>
          ))}
          {cost.tax_monthly > 0 && (
            <tr className="text-sm text-neutral-500">
              <td colSpan={4} className="py-1 pr-4">Tax ({cost.tax_rate_percent}%)</td>
              <td className="py-1 pr-4 text-right">{formatCurrency(cost.tax_monthly, cost.currency)}</td>
            </tr>
          )}
          {cost.support_monthly > 0 && (
            <tr className="text-sm text-neutral-500">
              <td colSpan={4} className="py-1 pr-4">Support ({cost.support_plan_percent}%)</td>
              <td className="py-1 pr-4 text-right">{formatCurrency(cost.support_monthly, cost.currency)}</td>
            </tr>
          )}
          <tr className="border-t border-neutral-200 text-base font-semibold dark:border-neutral-800">
            <td colSpan={4} className="py-2 pr-4">Total (monthly)</td>
            <td className="py-2 pr-4 text-right">{formatCurrency(cost.total_monthly, cost.currency)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
