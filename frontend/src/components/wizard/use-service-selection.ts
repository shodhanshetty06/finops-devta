"use client";

// Local, New-Estimate-page-only state for the GCP service catalog picker.
// Deliberately separate from use-wizard-state.ts so /questionnaire and
// /projects/[id]/new (which reuse that hook) are completely unaffected.
import { useCallback, useMemo, useState } from "react";

import type { ConfigFieldSchema, GCPServiceDefinition, ServiceSelection } from "@/lib/types";

export interface SelectedServiceEntry {
  key: string;
  service_id: string;
  config: Record<string, unknown>;
  // Explicit count of identical resources this entry represents (e.g. 4
  // Cloud Run services with the same vCPU/memory config) - always what the
  // user typed, defaulting to 1; never inferred from the resource name or
  // from adding multiple entries.
  quantity: number;
}

function defaultConfigFor(schema: ConfigFieldSchema[]): Record<string, unknown> {
  const config: Record<string, unknown> = {};
  for (const field of schema) {
    if (field.default !== null && field.default !== undefined) {
      config[field.field_id] = field.default;
    }
  }
  return config;
}

let nextKey = 0;
function generateKey(): string {
  nextKey += 1;
  return `svc-${Date.now()}-${nextKey}`;
}

export function useServiceSelection() {
  const [entries, setEntries] = useState<SelectedServiceEntry[]>([]);

  const addService = useCallback((definition: GCPServiceDefinition) => {
    setEntries((prev) => [
      ...prev,
      { key: generateKey(), service_id: definition.service_id, config: defaultConfigFor(definition.configuration_schema), quantity: 1 },
    ]);
  }, []);

  const updateServiceConfig = useCallback((key: string, config: Record<string, unknown>) => {
    setEntries((prev) => prev.map((entry) => (entry.key === key ? { ...entry, config } : entry)));
  }, []);

  const updateServiceQuantity = useCallback((key: string, quantity: number) => {
    setEntries((prev) => prev.map((entry) => (entry.key === key ? { ...entry, quantity: Math.max(1, Math.floor(quantity) || 1) } : entry)));
  }, []);

  const removeService = useCallback((key: string) => {
    setEntries((prev) => prev.filter((entry) => entry.key !== key));
  }, []);

  const duplicateService = useCallback((key: string) => {
    setEntries((prev) => {
      const source = prev.find((entry) => entry.key === key);
      if (!source) return prev;
      return [...prev, { ...source, key: generateKey(), config: { ...source.config } }];
    });
  }, []);

  const selectedServiceIds = useMemo(() => new Set(entries.map((e) => e.service_id)), [entries]);

  const asServiceSelections = useMemo<ServiceSelection[]>(
    () => entries.map(({ service_id, config, quantity }) => ({ service_id, config, quantity })),
    [entries],
  );

  return {
    entries,
    addService,
    updateServiceConfig,
    updateServiceQuantity,
    removeService,
    duplicateService,
    selectedServiceIds,
    asServiceSelections,
  };
}

export type ServiceSelectionState = ReturnType<typeof useServiceSelection>;
