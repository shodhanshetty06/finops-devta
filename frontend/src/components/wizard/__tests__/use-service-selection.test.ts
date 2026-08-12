import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useServiceSelection } from "@/components/wizard/use-service-selection";
import type { GCPServiceDefinition } from "@/lib/types";

function makeDefinition(overrides: Partial<GCPServiceDefinition> = {}): GCPServiceDefinition {
  return {
    service_id: "pubsub",
    display_name: "Pub/Sub",
    category: "Messaging & Eventing",
    description: "Async messaging",
    icon: "send",
    configuration_schema: [
      { field_id: "messages_per_month", label: "Messages/month", field_type: "number", unit: null, default: 100_000_000, min_value: null, max_value: null, options: null, required: true, help_text: null, group: null },
      { field_id: "region", label: "Region", field_type: "text", unit: null, default: null, min_value: null, max_value: null, options: null, required: false, help_text: null, group: null },
    ],
    pricing_dimensions: [],
    legacy_binding: null,
    active: true,
    ...overrides,
  };
}

describe("useServiceSelection", () => {
  it("starts empty", () => {
    const { result } = renderHook(() => useServiceSelection());
    expect(result.current.entries).toEqual([]);
    expect(result.current.asServiceSelections).toEqual([]);
  });

  it("addService seeds config from the schema's default values", () => {
    const { result } = renderHook(() => useServiceSelection());
    act(() => result.current.addService(makeDefinition()));
    expect(result.current.entries).toHaveLength(1);
    expect(result.current.entries[0].service_id).toBe("pubsub");
    expect(result.current.entries[0].config).toEqual({ messages_per_month: 100_000_000 });
    expect(result.current.selectedServiceIds.has("pubsub")).toBe(true);
  });

  it("addService allows multiple entries of the same service", () => {
    const { result } = renderHook(() => useServiceSelection());
    act(() => {
      result.current.addService(makeDefinition());
      result.current.addService(makeDefinition());
    });
    expect(result.current.entries).toHaveLength(2);
    expect(result.current.entries[0].key).not.toBe(result.current.entries[1].key);
  });

  it("updateServiceConfig patches only the targeted entry", () => {
    const { result } = renderHook(() => useServiceSelection());
    act(() => {
      result.current.addService(makeDefinition());
      result.current.addService(makeDefinition({ service_id: "bigquery" }));
    });
    const [first, second] = result.current.entries;
    act(() => result.current.updateServiceConfig(first.key, { messages_per_month: 5 }));
    expect(result.current.entries.find((e) => e.key === first.key)?.config).toEqual({ messages_per_month: 5 });
    expect(result.current.entries.find((e) => e.key === second.key)?.config).toEqual({ messages_per_month: 100_000_000 });
  });

  it("removeService removes only the targeted entry", () => {
    const { result } = renderHook(() => useServiceSelection());
    act(() => {
      result.current.addService(makeDefinition());
      result.current.addService(makeDefinition({ service_id: "bigquery" }));
    });
    const keyToRemove = result.current.entries[0].key;
    act(() => result.current.removeService(keyToRemove));
    expect(result.current.entries).toHaveLength(1);
    expect(result.current.entries[0].service_id).toBe("bigquery");
  });

  it("duplicateService copies config under a new key", () => {
    const { result } = renderHook(() => useServiceSelection());
    act(() => result.current.addService(makeDefinition()));
    const original = result.current.entries[0];
    act(() => result.current.duplicateService(original.key));
    expect(result.current.entries).toHaveLength(2);
    expect(result.current.entries[1].key).not.toBe(original.key);
    expect(result.current.entries[1].config).toEqual(original.config);
  });

  it("asServiceSelections strips the local key before submission", () => {
    const { result } = renderHook(() => useServiceSelection());
    act(() => result.current.addService(makeDefinition()));
    expect(result.current.asServiceSelections).toEqual([
      { service_id: "pubsub", config: { messages_per_month: 100_000_000 }, quantity: 1 },
    ]);
  });

  it("addService defaults quantity to 1", () => {
    const { result } = renderHook(() => useServiceSelection());
    act(() => result.current.addService(makeDefinition()));
    expect(result.current.entries[0].quantity).toBe(1);
  });

  it("updateServiceQuantity patches only the targeted entry and floors/clamps to at least 1", () => {
    const { result } = renderHook(() => useServiceSelection());
    act(() => {
      result.current.addService(makeDefinition());
      result.current.addService(makeDefinition({ service_id: "bigquery" }));
    });
    const [first, second] = result.current.entries;
    act(() => result.current.updateServiceQuantity(first.key, 4));
    expect(result.current.entries.find((e) => e.key === first.key)?.quantity).toBe(4);
    expect(result.current.entries.find((e) => e.key === second.key)?.quantity).toBe(1);

    act(() => result.current.updateServiceQuantity(first.key, 0));
    expect(result.current.entries.find((e) => e.key === first.key)?.quantity).toBe(1);

    act(() => result.current.updateServiceQuantity(first.key, 2.9));
    expect(result.current.entries.find((e) => e.key === first.key)?.quantity).toBe(2);
  });

  it("duplicateService copies quantity under a new key", () => {
    const { result } = renderHook(() => useServiceSelection());
    act(() => result.current.addService(makeDefinition()));
    act(() => result.current.updateServiceQuantity(result.current.entries[0].key, 3));
    act(() => result.current.duplicateService(result.current.entries[0].key));
    expect(result.current.entries[1].quantity).toBe(3);
  });
});
