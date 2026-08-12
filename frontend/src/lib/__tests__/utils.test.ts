import { describe, expect, it } from "vitest";

import { cn, formatCurrency, formatDate, severityColor } from "@/lib/utils";

describe("formatCurrency", () => {
  it("formats USD with two decimal places", () => {
    expect(formatCurrency(1234.5, "USD")).toBe("$1,234.50");
  });

  it("formats zero correctly", () => {
    expect(formatCurrency(0, "USD")).toBe("$0.00");
  });

  it("supports other currencies", () => {
    expect(formatCurrency(10, "EUR")).toContain("10.00");
  });
});

describe("formatDate", () => {
  it("produces a non-empty human readable string", () => {
    const result = formatDate("2026-01-15T10:30:00Z");
    expect(result.length).toBeGreaterThan(0);
    expect(result).toMatch(/2026/);
  });
});

describe("severityColor", () => {
  it("returns distinct classes per severity", () => {
    const blocker = severityColor("blocker");
    const warning = severityColor("warning");
    const info = severityColor("info");
    expect(blocker).toContain("red");
    expect(warning).toContain("amber");
    expect(info).toContain("blue");
    expect(new Set([blocker, warning, info]).size).toBe(3);
  });
});

describe("cn", () => {
  it("merges class names and resolves tailwind conflicts", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
    expect(cn("text-sm", undefined, "font-bold")).toBe("text-sm font-bold");
  });
});
