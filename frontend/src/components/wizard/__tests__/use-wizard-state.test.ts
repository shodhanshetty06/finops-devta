import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { emptyRequirement, useWizardState, WIZARD_STEPS } from "@/components/wizard/use-wizard-state";

describe("useWizardState", () => {
  it("starts with an empty requirement and business sizing mode", () => {
    const { result } = renderHook(() => useWizardState());
    expect(result.current.requirement).toEqual(emptyRequirement());
    expect(result.current.sizingMode).toBe("business");
    expect(result.current.stepIndex).toBe(0);
  });

  it("infers explicit sizing mode when initialized with a compute spec", () => {
    const initial = {
      ...emptyRequirement(),
      compute: {
        machine_family: "n2" as const, vcpu: 4, ram_gb: 16, instance_count: 1, gpu_type: "none" as const, gpu_count: 0,
        provisioning_model: "on_demand" as const, operating_system: "linux" as const, hours_per_day: null, days_per_month: null,
      },
    };
    const { result } = renderHook(() => useWizardState(initial));
    expect(result.current.sizingMode).toBe("explicit");
  });

  it("setSizing('explicit') populates compute and clears business", () => {
    const { result } = renderHook(() => useWizardState());
    act(() => result.current.setSizing("explicit"));
    expect(result.current.sizingMode).toBe("explicit");
    expect(result.current.requirement.compute).not.toBeNull();
    expect(result.current.requirement.business).toBeNull();
  });

  it("setSizing('business') populates business and clears compute", () => {
    const { result } = renderHook(() => useWizardState());
    act(() => result.current.setSizing("explicit"));
    act(() => result.current.setSizing("business"));
    expect(result.current.requirement.compute).toBeNull();
    expect(result.current.requirement.business).not.toBeNull();
  });

  it("toggleSection adds the section with defaults when enabled", () => {
    const { result } = renderHook(() => useWizardState());
    act(() => result.current.toggleSection("storage", true, result.current.defaults.storage));
    expect(result.current.requirement.storage).toEqual(result.current.defaults.storage);
  });

  it("toggleSection clears the section when disabled", () => {
    const { result } = renderHook(() => useWizardState());
    act(() => result.current.toggleSection("storage", true, result.current.defaults.storage));
    act(() => result.current.toggleSection("storage", false, result.current.defaults.storage));
    expect(result.current.requirement.storage).toBeNull();
  });

  it("update() patches a single top-level field without touching others", () => {
    const { result } = renderHook(() => useWizardState());
    act(() => result.current.update("project_name", "My Project"));
    expect(result.current.requirement.project_name).toBe("My Project");
    expect(result.current.requirement.region).toBe("us-central1");
  });

  it("goNext/goBack move within step bounds and never go out of range", () => {
    const { result } = renderHook(() => useWizardState());
    act(() => result.current.goBack());
    expect(result.current.stepIndex).toBe(0);
    for (let i = 0; i < WIZARD_STEPS.length + 3; i++) {
      act(() => result.current.goNext());
    }
    expect(result.current.stepIndex).toBe(WIZARD_STEPS.length - 1);
  });

  it("goToStep clamps to valid range", () => {
    const { result } = renderHook(() => useWizardState());
    act(() => result.current.goToStep(999));
    expect(result.current.stepIndex).toBe(WIZARD_STEPS.length - 1);
    act(() => result.current.goToStep(-5));
    expect(result.current.stepIndex).toBe(0);
  });
});
