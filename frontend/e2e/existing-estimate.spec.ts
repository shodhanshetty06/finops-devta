import { expect, test } from "@playwright/test";

import { registerAndLogin } from "./helpers";

// Existing Estimate journey (spec section 1B/23): starting from a project
// that already has Compute Engine sized, adding an unrelated service
// (Vertex AI) must show ONLY that service's configuration - Basics and
// Compute Engine sizing are never re-asked, just pre-filled and collapsed
// by default (Gap 4) - and the saved estimate's total updates afterward.
test("Existing Estimate: add a service without re-asking Basics/Sizing", async ({ page }) => {
  const { unique } = await registerAndLogin(page, "existing-estimate");
  const projectName = `E2E Existing ${unique}`;

  // -- Baseline: a saved estimate with Compute Engine only -----------------
  await page.goto("/estimate/new");
  await page.getByLabel("Project name").fill(projectName);
  await page.getByText("I know exactly what I need").click();
  await page.getByLabel("Instance count").fill("2");
  await page.getByLabel("vCPU (per instance)").fill("4");
  await page.getByLabel("RAM GB (per instance)").fill("16");
  await page.getByRole("button", { name: "Generate estimate" }).click();
  await expect(page.getByText("Priced instantly")).toBeVisible({ timeout: 45_000 });

  await page.getByRole("button", { name: "Save to a project" }).click();
  await expect(page.getByRole("heading", { name: "Save to a project" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save estimate" })).toBeEnabled();
  await page.getByRole("button", { name: "Save estimate" }).click();
  await expect(page).toHaveURL(/\/projects\/(\d+)\/estimates\/(\d+)/, { timeout: 45_000 });
  const match = page.url().match(/\/projects\/(\d+)\/estimates\/(\d+)/);
  const projectId = match![1];
  const baselineMonthly = await page.locator("text=/mo").first().textContent();

  // -- Existing Estimate: pick this project, add only Vertex AI -----------
  await page.goto(`/estimate/existing?project=${projectId}`);
  await expect(page.getByRole("heading", { name: "Existing estimate" })).toBeVisible();

  // Sizing starts collapsed with an "unchanged" summary - never re-asked.
  await expect(page.getByText(/Unchanged from v1/)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByLabel("Instance count")).toHaveCount(0);
  // Basics (project name) is nowhere on this page at all.
  await expect(page.getByLabel("Project name")).toHaveCount(0);

  await page.getByPlaceholder("Search GCP services...").fill("Vertex AI");
  const vertexCard = page.getByTestId("service-card-vertex-ai");
  await expect(vertexCard).toBeVisible();
  await vertexCard.getByRole("button", { name: "Add" }).click();
  await expect(page.getByLabel(/^Quantity for Vertex AI$/)).toBeVisible();

  // Still nothing but the new service and the unchanged-sizing summary -
  // no Compute Engine field, no other unrelated resource, appeared.
  await expect(page.getByLabel("vCPU (per instance)")).toHaveCount(0);

  await page.getByRole("button", { name: "Update existing estimate" }).click();
  await expect(page.getByText(/Updated to v2/)).toBeVisible({ timeout: 45_000 });

  await page.getByRole("link", { name: "View in project" }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/estimates/2`));
  const resourceTable = page.getByTestId("resource-summary-table");
  await expect(resourceTable.getByRole("cell", { name: /^Compute Engine/ }).first()).toBeVisible();
  await expect(resourceTable.getByRole("cell", { name: /^Vertex AI/ }).first()).toBeVisible();
  expect(baselineMonthly).toBeTruthy();
});
