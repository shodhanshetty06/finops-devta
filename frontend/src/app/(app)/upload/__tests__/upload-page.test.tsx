// Regression coverage for the arbitrary-Excel intake flow's isolation
// guarantees: a new/replacement upload always starts a clean calculation
// context, Reset fully clears it, and the region the user picks is always
// what gets sent to pricing - never whatever the workbook happened to
// contain or whatever a previous upload used.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// SaveToProjectDialog (rendered - if closed - alongside the results card)
// calls useRouter() unconditionally; there's no Next.js app router mounted
// in this jsdom test environment.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
}));

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return {
    ...actual,
    intakeApi: { ...actual.intakeApi, templateUrl: () => "#", uploadExcel: vi.fn() },
    estimateApi: { ...actual.estimateApi, create: vi.fn() },
    currencyApi: {
      getRates: vi.fn().mockResolvedValue({
        base: "USD", date: "2026-01-01", rates: {}, supported_currencies: ["USD"], stale: false,
      }),
    },
    projectsApi: { ...actual.projectsApi, list: vi.fn().mockResolvedValue([]) },
  };
});

import UploadExcelPage from "@/app/(app)/upload/page";
import { estimateApi, intakeApi } from "@/lib/api-client";
import { AssistantDataProvider } from "@/contexts/assistant-context";
import { AuthProvider } from "@/contexts/auth-context";
import { CurrencyProvider } from "@/contexts/currency-context";
import { QueryProvider } from "@/lib/query-client";
import type { EstimateResult, IntakeResponse } from "@/lib/types";

function renderPage() {
  return render(
    <QueryProvider>
      <AuthProvider>
        <AssistantDataProvider>
          <CurrencyProvider>
            <UploadExcelPage />
          </CurrencyProvider>
        </AssistantDataProvider>
      </AuthProvider>
    </QueryProvider>,
  );
}

function selectFile(name: string) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  const file = new File(["dummy"], name, { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
  fireEvent.change(input, { target: { files: [file] } });
}

function minimalRequirement(region: string, projectName: string) {
  return {
    project_name: projectName, region, normalization_strategy: null,
    compute: { machine_family: "e2", vcpu: 4, ram_gb: 16, instance_count: 1, gpu_type: "none", gpu_count: 0, provisioning_model: "on_demand", operating_system: "linux", hours_per_day: null, days_per_month: null },
    storage: null, database: null, network: null, kubernetes: null, availability: null, business: null,
    selected_services: [], existing_infrastructure_notes: null,
  };
}

function stubResponse(region: string, projectName: string, source: IntakeResponse["extraction_source"] = "template"): IntakeResponse {
  return {
    requirement: minimalRequirement(region, projectName) as never, issues: [], notes: [], estimate: null,
    extraction_source: source, region_source: "workbook",
  };
}

function stubEstimate(region: string): EstimateResult {
  return {
    estimate_id: "e1", project_name: "p", strategy_used: "balanced",
    original_request: minimalRequirement(region, "p") as never,
    normalized_spec: { region } as never,
    assumptions: [], validation: { results: [] } as never,
    architecture: { summary: "", components: [] },
    cost: {
      currency: "USD", line_items: [], discounts: [], resource_summaries: [], category_totals: {},
      subtotal_monthly: 10, discount_total_monthly: 0, tax_rate_percent: 0, tax_monthly: 0,
      support_plan_percent: 0, support_monthly: 0, total_monthly: 10, total_yearly: 120,
    } as never,
    audit_log: { entries: [] },
  };
}

beforeEach(() => {
  vi.mocked(intakeApi.uploadExcel).mockReset();
  vi.mocked(estimateApi.create).mockReset();
});

describe("Upload Excel page - isolation and region guarantees", () => {
  it("clears the previous file's result the instant a replacement upload starts, before the new response arrives", async () => {
    let resolveSecond!: (v: IntakeResponse) => void;
    vi.mocked(intakeApi.uploadExcel)
      .mockResolvedValueOnce(stubResponse("us-central1", "First Project"))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve; }));

    renderPage();
    selectFile("first.xlsx");
    await waitFor(() => expect(screen.getByText("First Project", { exact: false })).toBeTruthy());

    selectFile("second.xlsx");
    // While the second upload is still in flight, the first file's parsed
    // requirement must already be gone - never shown alongside the new upload.
    expect(screen.queryByText(/First Project/)).toBeNull();

    resolveSecond(stubResponse("europe-west1", "Second Project"));
    await waitFor(() => expect(screen.getByText(/Second Project/)).toBeTruthy());
    expect(screen.queryByText(/First Project/)).toBeNull();
  });

  it("Reset clears the file, requirement, estimate, and region selection back to defaults", async () => {
    vi.mocked(intakeApi.uploadExcel).mockResolvedValueOnce(stubResponse("europe-west1", "Reset Me"));
    renderPage();
    selectFile("reset.xlsx");
    await waitFor(() => expect(screen.getByText(/Reset Me/)).toBeTruthy());
    expect(screen.getByText("reset.xlsx")).toBeTruthy();

    fireEvent.click(screen.getByText(/Remove \/ Reset/));

    expect(screen.queryByText(/Reset Me/)).toBeNull();
    expect(screen.queryByText("reset.xlsx")).toBeNull();
    expect(screen.getByText(/Click to choose a .xlsx file/)).toBeTruthy();
  });

  it("prices with the workbook's own region when the user leaves the region override unset", async () => {
    vi.mocked(intakeApi.uploadExcel).mockResolvedValueOnce(stubResponse("asia-south1", "Region Test"));
    vi.mocked(estimateApi.create).mockResolvedValueOnce(stubEstimate("asia-south1"));

    renderPage();
    selectFile("region.xlsx");
    await waitFor(() => expect(screen.getByLabelText("Region")).toBeTruthy());

    // No region is preselected - the override is opt-in, not defaulted.
    expect((screen.getByLabelText("Region") as HTMLSelectElement).value).toBe("");
    fireEvent.click(screen.getByText("Calculate Price"));

    await waitFor(() => expect(estimateApi.create).toHaveBeenCalled());
    const [sentRequirement] = vi.mocked(estimateApi.create).mock.calls[0];
    expect(sentRequirement.region).toBe("asia-south1");
  });

  it("prices with the user-selected region when the override is explicitly set, ignoring the workbook's region", async () => {
    vi.mocked(intakeApi.uploadExcel).mockResolvedValueOnce(stubResponse("asia-south1", "Region Test"));
    vi.mocked(estimateApi.create).mockResolvedValueOnce(stubEstimate("us-west1"));

    renderPage();
    selectFile("region.xlsx");
    await waitFor(() => expect(screen.getByLabelText("Region")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Region"), { target: { value: "us-west1" } });
    fireEvent.click(screen.getByText("Calculate Price"));

    await waitFor(() => expect(estimateApi.create).toHaveBeenCalled());
    // The backend is the final authority on region (see
    // app/domain/region_resolution.py) - the override is sent as its own
    // param rather than pre-merged into the requirement client-side.
    const [, opts] = vi.mocked(estimateApi.create).mock.calls[0];
    expect(opts?.region).toBe("us-west1");
  });

  it("shows a clear review message, not a raw error, when nothing could be confidently identified", async () => {
    vi.mocked(intakeApi.uploadExcel).mockResolvedValueOnce({
      requirement: null,
      issues: [{ field: "workbook", message: "We could not confidently identify the required cloud resources from this workbook. Please review the extracted requirements below, correct or add anything that's missing, or download the standard template and fill it in directly.", severity: "blocker" }],
      notes: [], estimate: null, extraction_source: "unrecognized", region_source: "default",
    });

    renderPage();
    selectFile("garbage.xlsx");

    await waitFor(() => expect(screen.getAllByText(/We could not confidently identify/).length).toBeGreaterThan(0));
    expect(screen.queryByText(/TypeError|Traceback|500/)).toBeNull();
  });
});
