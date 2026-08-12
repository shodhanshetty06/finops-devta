"use client";

import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useCurrency } from "@/contexts/currency-context";
import type { CostBreakdown } from "@/lib/types";

/** Full priced line-item breakdown, ending in subtotal -> discounts -> tax
 * -> support -> total. Used on the estimate result page and Reports.
 * Displayed in the user's chosen currency (see CurrencyProvider) - the
 * estimate is still priced and stored in its native currency underneath. */
export function PricingTable({ cost }: { cost: CostBreakdown }) {
  const { formatMoney } = useCurrency();
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Category</TableHead>
          <TableHead>Description</TableHead>
          <TableHead>Quantity</TableHead>
          <TableHead>Unit price</TableHead>
          <TableHead>Source</TableHead>
          <TableHead className="text-right">Monthly</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {cost.line_items.map((item, i) => (
          <TableRow key={`${item.sku_id ?? item.description}-${i}`}>
            <TableCell>
              <Badge variant="secondary">{item.category}</Badge>
            </TableCell>
            <TableCell className="whitespace-normal text-foreground">{item.description}</TableCell>
            <TableCell className="text-muted-foreground">
              {item.quantity.toLocaleString()} {item.unit}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {formatMoney(item.unit_price, item.currency)}/{item.unit}
            </TableCell>
            <TableCell className="text-muted-foreground">{item.source}</TableCell>
            <TableCell className="text-right font-medium">{formatMoney(item.monthly_amount, item.currency)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
      <TableFooter>
        <TableRow>
          <TableCell colSpan={5} className="text-muted-foreground">
            Subtotal
          </TableCell>
          <TableCell className="text-right">{formatMoney(cost.subtotal_monthly, cost.currency)}</TableCell>
        </TableRow>
        {cost.discounts.map((d) => (
          <TableRow key={d.name}>
            <TableCell colSpan={5} className="text-success-700 dark:text-success-400">
              {d.name} ({d.percent_off}%)
            </TableCell>
            <TableCell className="text-right text-success-700 dark:text-success-400">
              -{formatMoney(d.monthly_savings, cost.currency)}
            </TableCell>
          </TableRow>
        ))}
        {cost.tax_monthly > 0 && (
          <TableRow>
            <TableCell colSpan={5} className="text-muted-foreground">
              Tax ({cost.tax_rate_percent}%)
            </TableCell>
            <TableCell className="text-right text-muted-foreground">{formatMoney(cost.tax_monthly, cost.currency)}</TableCell>
          </TableRow>
        )}
        {cost.support_monthly > 0 && (
          <TableRow>
            <TableCell colSpan={5} className="text-muted-foreground">
              Support ({cost.support_plan_percent}%)
            </TableCell>
            <TableCell className="text-right text-muted-foreground">{formatMoney(cost.support_monthly, cost.currency)}</TableCell>
          </TableRow>
        )}
        <TableRow className="hover:bg-transparent">
          <TableCell colSpan={5} className="text-base font-semibold text-foreground">
            Total (monthly)
          </TableCell>
          <TableCell className="text-right text-base font-semibold text-foreground">
            {formatMoney(cost.total_monthly, cost.currency)}
          </TableCell>
        </TableRow>
      </TableFooter>
    </Table>
  );
}
