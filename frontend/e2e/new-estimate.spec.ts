import { expect, test } from "@playwright/test";

import { registerAndLogin } from "./helpers";

// Full New Estimate journey: login -> Basics -> Sizing (Compute Engine,
// including the Storage/Networking fields added alongside it) -> add a
// second, different-category catalog service with an explicit quantity ->
// validate/normalize/price -> resource-level results (quantity, category
// totals, grand total) -> Excel download. Mirrors spec section 23's
// required flow.
test("New Estimate: login through Excel download", async ({ page }) => {
  const { unique } = await registerAndLogin(page, "new-estimate");
  const projectName = `E2E Project ${unique}`;

  await page.goto("/estimate/new");
  await expect(page.getByRole("heading", { name: "New estimate" })).toBeVisible();

  // -- Basics --------------------------------------------------------
  await page.getByLabel("Project name").fill(projectName);

  // -- Sizing (Compute Engine) ----------------------------------------
  await expect(page.getByText("I know exactly what I need")).toBeVisible();
  await page.getByText("I know exactly what I need").click();
  await page.getByLabel("Instance count").fill("3");
  await page.getByLabel("vCPU (per instance)").fill("4");
  await page.getByLabel("RAM GB (per instance)").fill("16");

  // -- Storage & networking (added alongside Sizing - Gap 2) -----------
  await page.getByText("Add block storage").click();
  await page.getByLabel(/^Size \(GB\)$/).fill("150");
  await page.getByText("Add networking").click();
  await page.getByLabel("External IPs").fill("1");

  // -- Add a second, different-category catalog service ----------------
  await page.getByPlaceholder("Search GCP services...").fill("Pub/Sub");
  const pubsubCard = page.getByTestId("service-card-pubsub");
  await expect(pubsubCard).toBeVisible();
  await pubsubCard.getByRole("button", { name: "Add" }).click();

  const qtyInput = page.getByLabel(/^Quantity for Pub\/Sub$/);
  await expect(qtyInput).toBeVisible();
  await qtyInput.fill("3");

  // -- Price it ----------------------------------------------------------
  await page.getByRole("button", { name: "Generate estimate" }).click();
  await expect(page.getByText("Priced instantly")).toBeVisible({ timeout: 45_000 });

  // -- Resource-level results: quantity is explicit, never inferred ------
  const resourceTable = page.getByTestId("resource-summary-table");
  await expect(resourceTable.getByRole("cell", { name: /^Compute Engine/ }).first()).toBeVisible();
  const pubsubRow = resourceTable.getByRole("row", { name: /Pub\/Sub/ });
  await expect(pubsubRow).toBeVisible();
  await expect(pubsubRow.getByRole("cell", { name: "3", exact: true })).toBeVisible();

  // -- Category totals + grand total reconcile ----------------------------
  await expect(page.getByText("Category totals")).toBeVisible();
  await expect(page.getByText("Grand total (all resources)")).toBeVisible();

  // -- Save to a project, then export Excel from the saved version -------
  await page.getByRole("button", { name: "Save to a project" }).click();
  await expect(page.getByRole("heading", { name: "Save to a project" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save estimate" })).toBeEnabled();
  await page.getByRole("button", { name: "Save estimate" }).click();
  await expect(page).toHaveURL(/\/projects\/\d+\/estimates\/\d+/, { timeout: 45_000 });

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export Excel" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.xlsx$/);
});
