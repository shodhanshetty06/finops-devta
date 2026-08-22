"use client";

// Lets whichever page currently has an already-computed EstimateResult and/or
// ScenarioComparison on screen hand it to the globally-mounted FinOps
// Assistant widget (frontend/src/components/ai-assistant.tsx), so the
// backend (backend/app/services/assistant_service.py) can ground its answers
// in real figures instead of guessing. Nothing here computes or transforms a
// price - it only carries whatever object the page already has, verbatim,
// the same way ReportRequest/ExplanationRequest do on the backend.
//
// Pages opt in with useSetAssistantEstimate(result)/useSetAssistantComparison
// (comparison) - a one-line hook call that registers on mount/update and
// automatically clears when the page unmounts, so the assistant never
// answers from a stale estimate a user has since navigated away from.
import { createContext, useContext, useEffect, useState } from "react";

import type { EstimateResult, ScenarioComparison } from "@/lib/types";

interface AssistantContextValue {
  estimate: EstimateResult | null;
  comparison: ScenarioComparison | null;
  setEstimate: (estimate: EstimateResult | null) => void;
  setComparison: (comparison: ScenarioComparison | null) => void;
}

const AssistantContext = createContext<AssistantContextValue | undefined>(undefined);

export function AssistantDataProvider({ children }: { children: React.ReactNode }) {
  const [estimate, setEstimate] = useState<EstimateResult | null>(null);
  const [comparison, setComparison] = useState<ScenarioComparison | null>(null);

  return (
    <AssistantContext.Provider value={{ estimate, comparison, setEstimate, setComparison }}>
      {children}
    </AssistantContext.Provider>
  );
}

function useAssistantContext(): AssistantContextValue {
  const ctx = useContext(AssistantContext);
  if (!ctx) throw new Error("useAssistantContext must be used within an AssistantDataProvider");
  return ctx;
}

/** Read-only access for the widget itself. */
export function useAssistantData(): { estimate: EstimateResult | null; comparison: ScenarioComparison | null } {
  const { estimate, comparison } = useAssistantContext();
  return { estimate, comparison };
}

/** Registers `estimate` as the assistant's current estimate context for as
 * long as the calling component is mounted (and whenever it changes); clears
 * it on unmount. Pass `null` for "loading"/"not available yet". */
export function useSetAssistantEstimate(estimate: EstimateResult | null): void {
  const { setEstimate } = useAssistantContext();
  useEffect(() => {
    setEstimate(estimate);
    return () => setEstimate(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estimate]);
}

/** Same as useSetAssistantEstimate, for the current scenario comparison. */
export function useSetAssistantComparison(comparison: ScenarioComparison | null): void {
  const { setComparison } = useAssistantContext();
  useEffect(() => {
    setComparison(comparison);
    return () => setComparison(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [comparison]);
}
