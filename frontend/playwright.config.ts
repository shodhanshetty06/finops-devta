import path from "path";
import { defineConfig, devices } from "@playwright/test";

// Real-browser E2E tests against the actual dev servers (not mocked) - see
// docs/PHASE6_NOTES.md, which flagged this as the natural next step after
// Phase 6's Vitest/RTL coverage. Both servers are started automatically
// (reusing already-running ones locally, e.g. via start-finance-guru.ps1)
// so `npx playwright test` works standalone in CI too.
export default defineConfig({
  testDir: "./e2e",
  // Generous margin for this environment's slow (network-mapped) drive,
  // where a cold Turbopack route compile has been observed to take minutes
  // the very first time a route is hit - see playwright.config.ts's
  // webServer entry below. Routes are pre-warmed before a real run, so this
  // is a safety margin, not the expected per-test duration.
  timeout: 180_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:6001",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    navigationTimeout: 60_000,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command: 'venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
      cwd: path.resolve(__dirname, "../backend"),
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: true,
      // Observed occasionally slow to spawn on this environment's network
      // drive (process/module lookup latency, not app startup time - the
      // app itself logs "Application startup complete" in under a second
      // once the process actually starts).
      timeout: 120_000,
      env: { FINOPS_PRICING_PROVIDER: "mock" },
    },
    {
      command: "npx next dev --turbopack -p 6001",
      cwd: __dirname,
      url: "http://localhost:6001",
      reuseExistingServer: true,
      // This project's working directory sits on a slow (network-mapped)
      // drive - `next dev --turbopack`'s own startup benchmark measured a
      // 528ms filesystem round-trip here, so the default 120s budget isn't
      // enough for a cold compile.
      timeout: 300_000,
    },
  ],
});
