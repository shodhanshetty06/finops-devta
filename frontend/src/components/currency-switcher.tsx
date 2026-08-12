"use client";

import { Check, Coins } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useCurrency } from "@/contexts/currency-context";

export function CurrencySwitcher() {
  const { displayCurrency, setDisplayCurrency, supportedCurrencies, isStale, isLoading } = useCurrency();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="flex h-9 items-center gap-1.5 rounded-md px-2.5 text-muted-foreground hover:bg-muted hover:text-foreground"
        aria-label="Change display currency"
      >
        <Coins className="h-4 w-4" />
        <span className="text-xs font-medium tabular-nums">{displayCurrency}</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuLabel>Display currency</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {supportedCurrencies.map((currency) => (
          <DropdownMenuItem key={currency} onSelect={() => setDisplayCurrency(currency)}>
            <span className="flex w-full items-center justify-between">
              {currency}
              {currency === displayCurrency && <Check className="h-3.5 w-3.5" />}
            </span>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <p className="px-2.5 pb-1.5 text-[11px] text-muted-foreground">
          {isLoading
            ? "Loading live rates…"
            : isStale
              ? "Showing last known rates (live refresh failed)"
              : "Amounts are priced in USD, converted for display using live rates."}
        </p>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
