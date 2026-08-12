import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ValidationPanel } from "@/components/validation-panel";
import type { ValidationReport } from "@/lib/types";

function makeReport(overrides: Partial<ValidationReport["results"][number]>[]): ValidationReport {
  return {
    results: overrides.map((o, i) => ({
      field: `field${i}`,
      rule: "some_rule",
      requested_value: "8",
      supported_value: "4",
      is_valid: false,
      severity: "warning",
      reason: "reason",
      recommendation: "recommendation",
      ...o,
    })),
  };
}

describe("ValidationPanel", () => {
  it("shows a success message when there are no results", () => {
    render(<ValidationPanel report={{ results: [] }} />);
    expect(screen.getByText(/no issues found/i)).toBeInTheDocument();
  });

  it("shows a loading message while validating", () => {
    render(<ValidationPanel report={null} isLoading />);
    expect(screen.getByText(/checking against supported/i)).toBeInTheDocument();
  });

  it("counts blockers, warnings, and infos separately", () => {
    const report = makeReport([{ severity: "blocker" }, { severity: "warning" }, { severity: "warning" }, { severity: "info" }]);
    render(<ValidationPanel report={report} />);
    expect(screen.getByText("1 blocker")).toBeInTheDocument();
    expect(screen.getByText("2 warnings")).toBeInTheDocument();
    expect(screen.getByText("1 note")).toBeInTheDocument();
  });

  it("orders blockers before warnings before infos", () => {
    const report = makeReport([
      { severity: "info", field: "field_info" },
      { severity: "blocker", field: "field_blocker" },
      { severity: "warning", field: "field_warning" },
    ]);
    render(<ValidationPanel report={report} />);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("field_blocker");
    expect(items[1]).toHaveTextContent("field_warning");
    expect(items[2]).toHaveTextContent("field_info");
  });

  it("shows the requested-to-supported value substitution when present", () => {
    const report = makeReport([{ requested_value: "8", supported_value: "4" }]);
    render(<ValidationPanel report={report} />);
    expect(screen.getByText(/requested 8/i)).toBeInTheDocument();
  });
});
