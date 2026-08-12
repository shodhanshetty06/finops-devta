"use client";

// Lets the whole app display already-priced amounts (everything is priced
// and stored in USD by the backend - see Settings.default_currency) in the
// user's preferred currency for viewing. Nothing is re-priced anywhere -
// this is purely presentational, using live rates from
// GET /api/v1/currency/rates (backend/app/pricing/currency_converter.py).
//
// A rate is never guessed: if live rates haven't loaded yet, or the chosen
// currency isn't in the fetched set, convert()/formatMoney() fall back to
// rendering the original amount in its original currency rather than
// showing a made-up number.
import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState } from "react";

import { currencyApi } from "@/lib/api-client";
import { getDisplayCurrency, setDisplayCurrency as persistDisplayCurrency } from "@/lib/preferences";
import { formatCurrency } from "@/lib/utils";

const FALLBACK_SUPPORTED_CURRENCIES = ["USD", "INR", "EUR", "GBP", "JPY", "AUD", "CAD", "SGD", "AED", "CNY"];

interface ConvertedAmount {
  amount: number;
  currency: string;
}

interface CurrencyContextValue {
  displayCurrency: string;
  setDisplayCurrency: (currency: string) => void;
  supportedCurrencies: string[];
  /** Converts `amount` (priced in `fromCurrency`) into the user's chosen
   * display currency. Falls back to the original amount+currency, unchanged,
   * whenever a live rate isn't available - never fabricates a number. */
  convert: (amount: number, fromCurrency: string) => ConvertedAmount;
  /** convert() + formatCurrency() in one call - what render sites use. */
  formatMoney: (amount: number, fromCurrency: string) => string;
  /** True when rates are being shown from a stale cache because the last
   * live refresh failed (still a real previously-fetched rate, just old). */
  isStale: boolean;
  isLoading: boolean;
}

const CurrencyContext = createContext<CurrencyContextValue | undefined>(undefined);

export function CurrencyProvider({ children }: { children: React.ReactNode }) {
  // Same hydration-safe-mount pattern as ThemeToggle: localStorage isn't
  // available during SSR, so the persisted preference is only read after
  // mount. Renders as USD (the backend's own pricing currency) until then.
  const [mounted, setMounted] = useState(false);
  const [displayCurrency, setDisplayCurrencyState] = useState("USD");

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDisplayCurrencyState(getDisplayCurrency());
    setMounted(true);
  }, []);

  const ratesQuery = useQuery({
    queryKey: ["currency-rates", "USD"],
    queryFn: () => currencyApi.getRates("USD"),
    staleTime: 60 * 60 * 1000, // rates only move a few times a day; matches the backend's own cache TTL order of magnitude
    retry: 1,
  });

  function setDisplayCurrency(currency: string) {
    setDisplayCurrencyState(currency);
    persistDisplayCurrency(currency);
  }

  function convert(amount: number, fromCurrency: string): ConvertedAmount {
    if (!mounted || fromCurrency === displayCurrency) return { amount, currency: fromCurrency };

    const rates = ratesQuery.data;
    if (!rates) return { amount, currency: fromCurrency }; // no live rates yet - show the real priced amount, don't guess

    // rates.rates is keyed off rates.base (USD) -> units of that currency per 1 USD.
    const fromRate = fromCurrency === rates.base ? 1 : rates.rates[fromCurrency];
    const toRate = displayCurrency === rates.base ? 1 : rates.rates[displayCurrency];
    if (fromRate === undefined || toRate === undefined) return { amount, currency: fromCurrency };

    const usdAmount = amount / fromRate;
    return { amount: Math.round(usdAmount * toRate * 100) / 100, currency: displayCurrency };
  }

  function formatMoney(amount: number, fromCurrency: string): string {
    const converted = convert(amount, fromCurrency);
    return formatCurrency(converted.amount, converted.currency);
  }

  const value: CurrencyContextValue = {
    displayCurrency,
    setDisplayCurrency,
    supportedCurrencies: ratesQuery.data?.supported_currencies ?? FALLBACK_SUPPORTED_CURRENCIES,
    convert,
    formatMoney,
    isStale: ratesQuery.data?.stale ?? false,
    isLoading: ratesQuery.isLoading,
  };

  return <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>;
}

export function useCurrency(): CurrencyContextValue {
  const ctx = useContext(CurrencyContext);
  if (!ctx) throw new Error("useCurrency must be used within a CurrencyProvider");
  return ctx;
}
