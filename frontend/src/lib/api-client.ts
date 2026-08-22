// Typed HTTP client for the GCP FinOps backend (see backend/app/api/routers/*).
// One axios instance, one place that knows about auth headers/401 handling,
// and one exported function per backend endpoint - components never build
// URLs or call axios directly, so an endpoint change only needs an edit here.
import axios, { type AxiosRequestConfig } from "axios";

import type {
  ApiErrorBody,
  AssistantChatResponse,
  AssistantMessagePayload,
  CarbonEstimate,
  CloudComparison,
  CloudSqlTierSpec,
  CommitmentRecommendation,
  CostForecast,
  CustomerRequirement,
  DiskTypeSpec,
  EstimateResult,
  EstimateVersionDetail,
  EstimateVersionSummary,
  ExchangeRatesResponse,
  GCPServiceDefinition,
  GkeConfig,
  GpuSpec,
  IntakeResponse,
  MachineTypeSpec,
  ProjectRead,
  RegionComparison,
  RegionSpec,
  RightsizingReport,
  ScenarioComparison,
  ScenarioRequest,
  Token,
  UsageMetrics,
  UserRead,
  UserRole,
  ValidationReport,
  VersionComparison,
  WorkloadStability,
} from "@/lib/types";
import { clearToken, getToken } from "@/lib/token";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const http = axios.create({ baseURL: API_BASE_URL });

http.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      clearToken();
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        // A hard navigation (not useRouter) is deliberate here: this runs
        // outside React (an axios interceptor), and a full reload is the
        // simplest way to guarantee every in-memory store (React Query
        // cache, component state) is wiped along with the expired session.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

/** Extracts a human-readable message from the backend's FinOpsError JSON
 * shape (`{error, message}` or, for 422 validation failures, `{error,
 * message, results}`) - falls back to the raw axios message for network
 * errors that never reached the server. */
export function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    return error.response?.data?.message ?? error.message;
  }
  if (error instanceof Error) return error.message;
  return "An unexpected error occurred.";
}

// -- Auth -----------------------------------------------------------------

export interface RegisterInput {
  email: string;
  password: string;
  full_name: string;
  role: UserRole;
}

export const authApi = {
  register: (data: RegisterInput) => http.post<UserRead>("/api/v1/auth/register", data).then((r) => r.data),

  login: (email: string, password: string) => {
    const body = new URLSearchParams();
    body.set("username", email);
    body.set("password", password);
    return http
      .post<Token>("/api/v1/auth/login", body, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      })
      .then((r) => r.data);
  },

  me: () => http.get<UserRead>("/api/v1/auth/me").then((r) => r.data),
};

// -- Stateless validate/estimate ------------------------------------------

export const estimateApi = {
  validate: (requirement: CustomerRequirement) =>
    http.post<ValidationReport>("/api/v1/validate", requirement).then((r) => r.data),

  create: (requirement: CustomerRequirement, opts?: { force?: boolean; commitmentTermYears?: number }) =>
    http
      .post<EstimateResult>("/api/v1/estimate", requirement, {
        params: { force: opts?.force ?? false, commitment_term_years: opts?.commitmentTermYears ?? 0 },
      })
      .then((r) => r.data),
};

// -- Catalog (for wizard dropdowns) ---------------------------------------

export const catalogApi = {
  machineTypes: (family?: string) =>
    http.get<MachineTypeSpec[]>("/api/v1/catalog/machine-types", { params: { family } }).then((r) => r.data),
  diskTypes: () => http.get<DiskTypeSpec[]>("/api/v1/catalog/disk-types").then((r) => r.data),
  gpuTypes: () => http.get<GpuSpec[]>("/api/v1/catalog/gpu-types").then((r) => r.data),
  regions: () => http.get<RegionSpec[]>("/api/v1/catalog/regions").then((r) => r.data),
  cloudSqlTiers: (engine?: string) =>
    http.get<CloudSqlTierSpec[]>("/api/v1/catalog/cloud-sql-tiers", { params: { engine } }).then((r) => r.data),
  gkeConfig: () => http.get<GkeConfig>("/api/v1/catalog/gke-config").then((r) => r.data),
  services: (params?: { search?: string; category?: string }) =>
    http.get<GCPServiceDefinition[]>("/api/v1/catalog/services", { params }).then((r) => r.data),
  serviceCategories: () => http.get<string[]>("/api/v1/catalog/services/categories").then((r) => r.data),
};

// -- Projects + versioned estimates ---------------------------------------

export const projectsApi = {
  list: () => http.get<ProjectRead[]>("/api/v1/projects").then((r) => r.data),

  create: (name: string) => http.post<ProjectRead>("/api/v1/projects", { name }).then((r) => r.data),

  get: (id: number) => http.get<ProjectRead>(`/api/v1/projects/${id}`).then((r) => r.data),

  listVersions: (id: number) =>
    http.get<EstimateVersionSummary[]>(`/api/v1/projects/${id}/estimates`).then((r) => r.data),

  getVersion: (id: number, version: number) =>
    http.get<EstimateVersionDetail>(`/api/v1/projects/${id}/estimates/${version}`).then((r) => r.data),

  createEstimateVersion: (
    id: number,
    requirement: CustomerRequirement,
    opts?: { force?: boolean; commitmentTermYears?: number },
  ) =>
    http
      .post<EstimateVersionDetail>(`/api/v1/projects/${id}/estimates`, {
        requirement,
        force: opts?.force ?? false,
        commitment_term_years: opts?.commitmentTermYears ?? 0,
      })
      .then((r) => r.data),

  createFromExcel: (id: number, file: File, opts?: { force?: boolean; commitmentTermYears?: number }) => {
    const formData = new FormData();
    formData.append("file", file);
    return http
      .post<EstimateVersionDetail>(`/api/v1/projects/${id}/intake/excel`, formData, {
        params: { force: opts?.force ?? false, commitment_term_years: opts?.commitmentTermYears ?? 0 },
      })
      .then((r) => r.data);
  },

  createFromText: (
    id: number,
    body: { project_name: string; text: string; region_hint?: string },
    opts?: { force?: boolean; commitmentTermYears?: number },
  ) =>
    http
      .post<EstimateVersionDetail>(`/api/v1/projects/${id}/intake/text`, body, {
        params: { force: opts?.force ?? false, commitment_term_years: opts?.commitmentTermYears ?? 0 },
      })
      .then((r) => r.data),

  // targetCurrency is sent as a query param (not the JSON body) because the
  // backend route's body IS a BrandingConfig, unembedded - adding a second
  // body field there would force FastAPI to nest it under keys and break
  // that existing flat shape (see the Query() comment in
  // backend/app/api/routers/projects.py).
  exportExcelUrl: (id: number, version: number, targetCurrency?: string) =>
    `/api/v1/projects/${id}/estimates/${version}/reports/excel${targetCurrency ? `?target_currency=${encodeURIComponent(targetCurrency)}` : ""}`,
  exportPdfUrl: (id: number, version: number, targetCurrency?: string) =>
    `/api/v1/projects/${id}/estimates/${version}/reports/pdf${targetCurrency ? `?target_currency=${encodeURIComponent(targetCurrency)}` : ""}`,

  compareVersions: (id: number, fromVersion: number, toVersion: number) =>
    http
      .get<VersionComparison>(`/api/v1/projects/${id}/estimates/compare`, {
        params: { from: fromVersion, to: toVersion },
      })
      .then((r) => r.data),
};

// -- Optimization (backend/app/api/routers/optimization.py) ---------------
// Read-only analyses over an already-priced CustomerRequirement - every
// dollar figure still comes from the same PricingProvider the estimate
// itself used, these endpoints never invent a price.

export const optimizationApi = {
  rightsizing: (requirement: CustomerRequirement, usage: UsageMetrics, force = false) =>
    http
      .post<RightsizingReport>("/api/v1/optimization/rightsizing", { requirement, usage, force })
      .then((r) => r.data),

  commitmentRecommendation: (requirement: CustomerRequirement, workloadStability: WorkloadStability, force = false) =>
    http
      .post<CommitmentRecommendation>("/api/v1/optimization/commitment-recommendation", {
        requirement,
        workload_stability: workloadStability,
        force,
      })
      .then((r) => r.data),

  forecast: (
    requirement: CustomerRequirement,
    opts: { monthlyGrowthPercent?: number; months?: number; force?: boolean; commitmentTermYears?: number } = {},
  ) =>
    http
      .post<CostForecast>("/api/v1/optimization/forecast", {
        requirement,
        monthly_growth_percent: opts.monthlyGrowthPercent ?? 0,
        months: opts.months ?? 12,
        force: opts.force ?? false,
        commitment_term_years: opts.commitmentTermYears ?? 0,
      })
      .then((r) => r.data),

  carbon: (requirement: CustomerRequirement, force = false) =>
    http.post<CarbonEstimate>("/api/v1/optimization/carbon", { requirement, force }).then((r) => r.data),

  compareRegions: (requirement: CustomerRequirement, regions: string[], force = true) =>
    http
      .post<RegionComparison>("/api/v1/optimization/compare-regions", { requirement, regions, force })
      .then((r) => r.data),

  compareScenarios: (
    base: CustomerRequirement,
    scenarios: ScenarioRequest[],
    opts: { force?: boolean; commitmentTermYears?: number } = {},
  ) =>
    http
      .post<ScenarioComparison>("/api/v1/optimization/compare-scenarios", {
        base,
        scenarios,
        force: opts.force ?? false,
        commitment_term_years: opts.commitmentTermYears ?? 0,
      })
      .then((r) => r.data),

  compareClouds: (requirement: CustomerRequirement, clouds: string[] = ["gcp", "aws", "azure"], force = true) =>
    http
      .post<CloudComparison>("/api/v1/optimization/compare-clouds", { requirement, clouds, force })
      .then((r) => r.data),
};

// -- Currency (display conversion only, never re-prices anything) ---------

export const currencyApi = {
  getRates: (base = "USD") =>
    http.get<ExchangeRatesResponse>("/api/v1/currency/rates", { params: { base } }).then((r) => r.data),
};

// -- Intake (stateless) -----------------------------------------------------

export const intakeApi = {
  templateUrl: () => `${API_BASE_URL}/api/v1/intake/excel/template`,

  uploadExcel: (file: File, autoEstimate: boolean) => {
    const formData = new FormData();
    formData.append("file", file);
    return http
      .post<IntakeResponse>("/api/v1/intake/excel", formData, { params: { auto_estimate: autoEstimate } })
      .then((r) => r.data);
  },

  extractText: (body: { project_name: string; text: string; region_hint?: string }, autoEstimate: boolean) =>
    http
      .post<IntakeResponse>("/api/v1/intake/text", body, { params: { auto_estimate: autoEstimate } })
      .then((r) => r.data),
};

// -- AI assistant chat (Phase 11, Groq) --------------------------------------

export const assistantApi = {
  // `estimate`/`comparison` - whatever already-computed EstimateResult /
  // ScenarioComparison the caller currently has on screen (see
  // frontend/src/contexts/assistant-context.tsx) - are forwarded verbatim so
  // the backend can ground its answer in real figures instead of guessing.
  chat: (
    message: string,
    history: AssistantMessagePayload[],
    context?: { estimate?: EstimateResult | null; comparison?: ScenarioComparison | null },
  ) =>
    http
      .post<AssistantChatResponse>("/api/v1/assistant/chat", {
        message,
        history,
        estimate: context?.estimate ?? null,
        comparison: context?.comparison ?? null,
      })
      .then((r) => r.data),
};

// -- Reports (stateless - renders an EstimateResult that isn't saved to a
// project yet, e.g. a quick upload/wizard estimate) ------------------------

export const reportsApi = {
  exportExcelUrl: () => "/api/v1/reports/excel",
  exportPdfUrl: () => "/api/v1/reports/pdf",
};

/** Downloads a report by streaming a POST response through axios (so the
 * Authorization header is attached) and saving it via a synthetic anchor -
 * a plain `<a href>` can't carry auth headers, and these export endpoints
 * require a logged-in user. */
export async function downloadReport(url: string, filename: string, body: unknown = {}, config?: AxiosRequestConfig) {
  const response = await http.post(url, body, { ...config, responseType: "blob" });
  const blobUrl = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(blobUrl);
}
