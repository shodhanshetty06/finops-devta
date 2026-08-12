import { expect, type Page } from "@playwright/test";

/** Registers a brand-new customer account (unique email per call) and lands
 * on the dashboard, authenticated - the starting point for every E2E flow
 * below. A fresh user per test run avoids any dependency on pre-seeded
 * fixture data in the dev database. */
export async function registerAndLogin(page: Page, namePrefix: string) {
  const unique = `${namePrefix}-${Date.now()}-${Math.floor(Math.random() * 10000)}`;
  // Not a `.test`/`.example`/`.invalid` TLD (RFC 2606 special-use domains) -
  // the backend's email validator (pydantic's EmailStr) rejects those as
  // non-deliverable, so a normal-looking fake commercial domain is needed.
  const email = `${unique}@e2e-playwright-mail.com`;

  await page.goto("/register");
  await page.getByLabel("Full name").fill(`E2E ${namePrefix}`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "Create account" }).click();
  // The very first request against a freshly-started backend on this
  // environment's network-mapped drive has been observed to take much
  // longer than steady-state requests (first SQLite file open/lock on a
  // network filesystem) - generous headroom here, not a steady-state bound.
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 45_000 });

  return { email, unique };
}
