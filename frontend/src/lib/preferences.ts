// Client-only preferences, persisted to localStorage. Deliberately not sent
// to the backend - there's no user-preferences endpoint (auth.py only has
// register/login/me), and these are genuinely local UI defaults, not
// account state that needs to sync across devices.
import type { NormalizationStrategy } from "@/lib/types";

const DEFAULT_STRATEGY_KEY = "finops:default-normalization-strategy";
const DISPLAY_CURRENCY_KEY = "finops:display-currency";

export function getDefaultNormalizationStrategy(): NormalizationStrategy {
  if (typeof window === "undefined") return "balanced";
  const stored = window.localStorage.getItem(DEFAULT_STRATEGY_KEY);
  if (stored === "conservative" || stored === "balanced" || stored === "performance") return stored;
  return "balanced";
}

export function setDefaultNormalizationStrategy(strategy: NormalizationStrategy): void {
  window.localStorage.setItem(DEFAULT_STRATEGY_KEY, strategy);
}

// The currency everything gets displayed in (cost cards, tables, dashboard,
// reports). Purely a display preference - estimates are still priced and
// stored in USD; see contexts/currency-context.tsx for the conversion.
export function getDisplayCurrency(): string {
  if (typeof window === "undefined") return "USD";
  return window.localStorage.getItem(DISPLAY_CURRENCY_KEY) || "USD";
}

export function setDisplayCurrency(currency: string): void {
  window.localStorage.setItem(DISPLAY_CURRENCY_KEY, currency);
}
