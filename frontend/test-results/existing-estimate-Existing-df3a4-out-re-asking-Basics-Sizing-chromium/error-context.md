# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: existing-estimate.spec.ts >> Existing Estimate: add a service without re-asking Basics/Sizing
- Location: e2e\existing-estimate.spec.ts:10:5

# Error details

```
Test timeout of 180000ms exceeded.
```

```
Error: locator.textContent: Test timeout of 180000ms exceeded.
Call log:
  - waiting for locator('text=/mo').first()

```

# Page snapshot

```yaml
- generic [active] [ref=f1e1]:
  - generic [ref=f1e2]:
    - complementary [ref=f1e3]:
      - generic [ref=f1e4]:
        - link "FinOps" [ref=f1e6] [cursor=pointer]:
          - /url: /dashboard
        - navigation "Primary" [ref=f1e11]:
          - generic [ref=f1e12]:
            - generic [ref=f1e13]:
              - paragraph [ref=f1e14]: Overview
              - link "Dashboard" [ref=f1e15] [cursor=pointer]:
                - /url: /dashboard
              - link "Projects" [ref=f1e22] [cursor=pointer]:
                - /url: /projects
            - generic [ref=f1e27]:
              - paragraph [ref=f1e28]: Build
              - link "New Estimate" [ref=f1e29] [cursor=pointer]:
                - /url: /estimate/new
              - link "Existing Estimates" [ref=f1e33] [cursor=pointer]:
                - /url: /estimate/existing
              - link "Upload Excel" [ref=f1e38] [cursor=pointer]:
                - /url: /upload
              - link "Project Questions" [ref=f1e43] [cursor=pointer]:
                - /url: /questionnaire
            - generic [ref=f1e48]:
              - paragraph [ref=f1e49]: Analyze
              - link "Cost Analysis" [ref=f1e50] [cursor=pointer]:
                - /url: /pricing
              - link "Resource Optimization" [ref=f1e56] [cursor=pointer]:
                - /url: /optimization
              - link "Validation" [ref=f1e62] [cursor=pointer]:
                - /url: /validation
              - link "Assumptions" [ref=f1e67] [cursor=pointer]:
                - /url: /normalization
              - link "Architecture" [ref=f1e70] [cursor=pointer]:
                - /url: /architecture
            - generic [ref=f1e77]:
              - paragraph [ref=f1e78]: Reporting
              - link "Reports" [ref=f1e79] [cursor=pointer]:
                - /url: /reports
              - link "History" [ref=f1e83] [cursor=pointer]:
                - /url: /history
            - generic [ref=f1e89]:
              - paragraph [ref=f1e90]: Workspace
              - link "Settings" [ref=f1e91] [cursor=pointer]:
                - /url: /settings
        - button "Collapse sidebar" [ref=f1e97]:
          - generic [ref=f1e101]: Collapse
    - generic [ref=f1e102]:
      - banner [ref=f1e103]:
        - navigation "Breadcrumb" [ref=f1e105]:
          - link "Projects" [ref=f1e106] [cursor=pointer]:
            - /url: /projects
          - link "#12" [ref=f1e109] [cursor=pointer]:
            - /url: /projects/12
          - link "Estimates" [ref=f1e112] [cursor=pointer]:
            - /url: /projects/12/estimates
          - generic [ref=f1e115]: "#1"
        - generic [ref=f1e116]:
          - button "Search everywhere" [ref=f1e117]:
            - generic [ref=f1e121]: Search...
            - generic [ref=f1e122]: Ctrl K
          - button [ref=f1e124]
          - button "USD" [ref=f1e129]
          - button "Toggle theme" [ref=f1e136]
          - button [ref=f1e140]:
            - generic [ref=f1e141]: EE
          - link "New estimate" [ref=f1e142] [cursor=pointer]:
            - /url: /estimate/new
      - main [ref=f1e143]:
        - generic [ref=f1e145]:
          - generic [ref=f1e146]:
            - generic [ref=f1e147]:
              - paragraph [ref=f1e148]:
                - link "E2E Existing existing-estimate-1788237365120-9823" [ref=f1e149] [cursor=pointer]:
                  - /url: /projects/12
                - text: › version 1
              - heading "Cost estimate" [level=1] [ref=f1e150]
              - paragraph [ref=f1e151]: "Generated Sep 1, 2026, 04:36 AM · strategy: balanced · region: asia-south1"
            - generic [ref=f1e152]:
              - link "Edit & recalculate" [ref=f1e153] [cursor=pointer]:
                - /url: /projects/12/new?from=1
              - generic [ref=f1e154]:
                - button "Export Excel" [ref=f1e155]
                - button "Export PDF" [ref=f1e159]
          - generic [ref=f1e163]:
            - generic [ref=f1e164]:
              - generic [ref=f1e165]:
                - paragraph [ref=f1e167]: Monthly
                - paragraph [ref=f1e171]: $170.63
              - generic [ref=f1e172]:
                - paragraph [ref=f1e174]: Yearly
                - paragraph [ref=f1e180]: $2,047.56
              - generic [ref=f1e181]:
                - paragraph [ref=f1e183]: 3-Year
                - paragraph [ref=f1e187]: $6,142.68
              - generic [ref=f1e188]:
                - paragraph [ref=f1e190]: Discounts applied
                - paragraph [ref=f1e195]: $42.66
                - generic [ref=f1e196]: Sustained Use Discount (20%)
            - generic [ref=f1e198]:
              - generic [ref=f1e199]:
                - heading "Cost breakdown by category" [level=3] [ref=f1e201]
                - generic [ref=f1e205]:
                  - list [ref=f1e207]:
                    - listitem [ref=f1e208]:
                      - img "Compute legend icon" [ref=f1e209]
                      - text: Compute
                  - application [ref=f1e211]:
                    - generic [ref=f1e218]: Compute
              - generic [ref=f1e221]:
                - heading "Cost projection" [level=3] [ref=f1e223]
                - application [ref=f1e228]:
                  - generic [ref=f1e245]:
                    - generic [ref=f1e246]:
                      - generic [ref=f1e247]: Monthly
                      - generic [ref=f1e249]: Yearly
                      - generic [ref=f1e251]: 3-Year
                    - generic [ref=f1e253]:
                      - generic [ref=f1e254]: $0.00
                      - generic [ref=f1e256]: $2,000.00
                      - generic [ref=f1e258]: $4,000.00
                      - generic [ref=f1e260]: $6,000.00
                      - generic [ref=f1e262]: $8,000.00
            - generic [ref=f1e264]:
              - heading "Selected resources" [level=3] [ref=f1e266]
              - generic [ref=f1e268]:
                - table [ref=f1e270]:
                  - rowgroup [ref=f1e271]:
                    - row [ref=f1e272]:
                      - columnheader [ref=f1e273]
                      - columnheader "Resource" [ref=f1e274]
                      - columnheader "Configuration" [ref=f1e275]
                      - columnheader "Quantity" [ref=f1e276]
                      - columnheader "Unit cost" [ref=f1e277]
                      - columnheader "Subtotal" [ref=f1e278]
                      - columnheader "Status" [ref=f1e279]
                  - rowgroup [ref=f1e280]:
                    - row [ref=f1e281] [cursor=pointer]:
                      - cell [ref=f1e282]
                      - cell "Compute Engine (Compute)" [ref=f1e285]:
                        - text: Compute Engine
                        - generic [ref=f1e286]: (Compute)
                      - cell "e2-standard-4, 4 vCPU / 16 GB RAM, linux, on_demand, 2 instance(s)" [ref=f1e287]
                      - cell "2" [ref=f1e288]
                      - cell "$106.65" [ref=f1e289]
                      - cell "$213.29" [ref=f1e290]
                      - cell "Valid" [ref=f1e291]
                  - rowgroup [ref=f1e296]:
                    - row [ref=f1e297]:
                      - cell [ref=f1e298]
                      - cell "$213.29" [ref=f1e299]
                      - cell [ref=f1e300]
                    - row [ref=f1e301]:
                      - cell "Grand total (all resources)" [ref=f1e302]
                      - cell [ref=f1e303]
                - generic [ref=f1e304]:
                  - paragraph [ref=f1e305]: Category totals
                  - generic [ref=f1e307]:
                    - generic [ref=f1e308]: Compute
                    - generic [ref=f1e309]: $213.29
            - generic [ref=f1e310]:
              - heading "Line items" [level=3] [ref=f1e312]
              - table [ref=f1e315]:
                - rowgroup [ref=f1e316]:
                  - row [ref=f1e317]:
                    - columnheader "Category" [ref=f1e318]
                    - columnheader "Description" [ref=f1e319]
                    - columnheader "Quantity" [ref=f1e320]
                    - columnheader "Unit price" [ref=f1e321]
                    - columnheader "Source" [ref=f1e322]
                    - columnheader "Monthly" [ref=f1e323]
                - rowgroup [ref=f1e324]:
                  - row [ref=f1e325]:
                    - cell "Compute" [ref=f1e326]
                    - cell "e2-standard-4 x 2 instance(s) (asia-south1)" [ref=f1e328]
                    - cell "1,460 hour" [ref=f1e329]
                    - cell "$0.15/hour" [ref=f1e330]
                    - cell "mock_catalog" [ref=f1e331]
                    - cell "$213.29" [ref=f1e332]
                - rowgroup [ref=f1e333]:
                  - row [ref=f1e334]:
                    - cell "Subtotal" [ref=f1e335]
                    - cell "$213.29" [ref=f1e336]
                  - row [ref=f1e337]:
                    - cell "Sustained Use Discount (20%)" [ref=f1e338]
                    - cell "-$42.66" [ref=f1e339]
                  - row [ref=f1e340]:
                    - cell "Total (monthly)" [ref=f1e341]
                    - cell "$170.63" [ref=f1e342]
            - generic [ref=f1e343]:
              - heading "Recommended architecture" [level=3] [ref=f1e345]
              - generic [ref=f1e347]:
                - paragraph [ref=f1e348]: "Recommended architecture for 'E2E Existing existing-estimate-1788237365120-9823' in asia-south1: 3 components spanning Backend, Monitoring, Security."
                - document [ref=f1e351]:
                  - generic [ref=f1e354]:
                    - paragraph [ref=f1e361]: BackendCompute Engine (e2-standard-4 x 2)
                    - paragraph [ref=f1e368]: MonitoringCloud Monitoring + Cloud Logging
                    - paragraph [ref=f1e375]: SecurityIAM least-privilege roles + Secret Manager
                - generic [ref=f1e376]:
                  - generic [ref=f1e377]:
                    - heading "Backend" [level=3] [ref=f1e379]
                    - generic [ref=f1e380]:
                      - paragraph [ref=f1e381]: Compute Engine (e2-standard-4 x 2)
                      - paragraph [ref=f1e382]: Directly sized VM instances matching the requested/normalized compute profile.
                  - generic [ref=f1e383]:
                    - heading "Monitoring" [level=3] [ref=f1e385]
                    - generic [ref=f1e386]:
                      - paragraph [ref=f1e387]: Cloud Monitoring + Cloud Logging
                      - paragraph [ref=f1e388]: Standard observability stack for metrics, uptime checks, and centralized logs.
                  - generic [ref=f1e389]:
                    - heading "Security" [level=3] [ref=f1e391]
                    - generic [ref=f1e392]:
                      - paragraph [ref=f1e393]: IAM least-privilege roles + Secret Manager
                      - paragraph [ref=f1e394]: Baseline access control and secrets management for any production workload.
            - generic [ref=f1e395]:
              - heading "Validation & assumptions 5" [level=3] [ref=f1e397]:
                - text: Validation & assumptions
                - generic [ref=f1e398]: "5"
              - generic [ref=f1e400]:
                - tablist [ref=f1e401]:
                  - tab "Validation (5)" [selected] [ref=f1e402]
                  - tab "Assumptions (0)" [ref=f1e403]
                - tabpanel [ref=f1e404]:
                  - table [ref=f1e406]:
                    - rowgroup [ref=f1e407]:
                      - row [ref=f1e408]:
                        - columnheader "Severity" [ref=f1e409]
                        - columnheader "Field" [ref=f1e410]
                        - columnheader "Requested" [ref=f1e411]
                        - columnheader "Supported" [ref=f1e412]
                        - columnheader "Reason" [ref=f1e413]
                        - columnheader "Recommendation" [ref=f1e414]
                    - rowgroup [ref=f1e415]:
                      - row [ref=f1e416]:
                        - cell "Info" [ref=f1e417]
                        - cell "compute.vcpu" [ref=f1e421]
                        - cell "4" [ref=f1e422]
                        - cell "4" [ref=f1e423]
                        - cell "4 vCPU is a supported configuration for the e2 family." [ref=f1e424]
                        - cell "No action needed." [ref=f1e425]
                      - row [ref=f1e426]:
                        - cell "Info" [ref=f1e427]
                        - cell "compute.ram_gb" [ref=f1e431]
                        - cell "16.0" [ref=f1e432]
                        - cell "16.0" [ref=f1e433]
                        - cell "16.0 GB RAM matches a supported machine type in the e2 family." [ref=f1e434]
                        - cell "No action needed." [ref=f1e435]
                      - row [ref=f1e436]:
                        - cell "Info" [ref=f1e437]
                        - cell "compute.machine_family" [ref=f1e441]
                        - cell "e2" [ref=f1e442]
                        - cell "e2" [ref=f1e443]
                        - cell "Requested vCPU/RAM combination maps directly to machine type 'e2-standard-4'." [ref=f1e444]
                        - cell "No action needed." [ref=f1e445]
                      - row [ref=f1e446]:
                        - cell "Info" [ref=f1e447]
                        - cell "compute.machine_family" [ref=f1e451]
                        - cell "e2 in asia-south1" [ref=f1e452]
                        - cell "e2 in asia-south1" [ref=f1e453]
                        - cell "The 'e2' machine family is available in 'asia-south1'." [ref=f1e454]
                        - cell "No action needed." [ref=f1e455]
                      - row [ref=f1e456]:
                        - cell "Info" [ref=f1e457]
                        - cell "region" [ref=f1e461]
                        - cell "asia-south1" [ref=f1e462]
                        - cell "asia-south1" [ref=f1e463]
                        - cell "'asia-south1' is a supported Google Cloud region." [ref=f1e464]
                        - cell "No action needed." [ref=f1e465]
          - generic [ref=f1e466]:
            - heading "Optimization" [level=3] [ref=f1e468]
            - generic [ref=f1e473]:
              - tablist [ref=f1e474]:
                - tab "Rightsizing" [selected] [ref=f1e475]
                - tab "Commitment" [ref=f1e476]
                - tab "Forecast" [ref=f1e477]
                - tab "Carbon" [ref=f1e478]
                - tab "Compare" [ref=f1e479]
              - tabpanel [ref=f1e480]:
                - generic [ref=f1e481]:
                  - paragraph [ref=f1e482]: This platform has no live monitoring integration - enter observed CPU utilization (e.g. from Cloud Monitoring) and the existing RightsizingEngine will compare current vs. resized cost through the real pricing pipeline.
                  - generic [ref=f1e483]:
                    - generic [ref=f1e484]:
                      - generic [ref=f1e485]: Avg CPU utilization (%)
                      - spinbutton "Avg CPU utilization (%)" [ref=f1e486]: "35"
                    - generic [ref=f1e487]:
                      - generic [ref=f1e488]: Peak CPU utilization (%)
                      - spinbutton "Peak CPU utilization (%)" [ref=f1e489]: "60"
                  - button "Analyze rightsizing" [ref=f1e490]
    - button "Open FinOps Assistant" [ref=f1e491]
  - region "Notifications alt+T"
  - button "Open Next.js Dev Tools" [ref=f1e500] [cursor=pointer]
  - alert [ref=f1e504]
  - generic [ref=f1e505]: $0.00
```

# Test source

```ts
  1  | import { expect, test } from "@playwright/test";
  2  | 
  3  | import { registerAndLogin } from "./helpers";
  4  | 
  5  | // Existing Estimate journey (spec section 1B/23): starting from a project
  6  | // that already has Compute Engine sized, adding an unrelated service
  7  | // (Vertex AI) must show ONLY that service's configuration - Basics and
  8  | // Compute Engine sizing are never re-asked, just pre-filled and collapsed
  9  | // by default (Gap 4) - and the saved estimate's total updates afterward.
  10 | test("Existing Estimate: add a service without re-asking Basics/Sizing", async ({ page }) => {
  11 |   const { unique } = await registerAndLogin(page, "existing-estimate");
  12 |   const projectName = `E2E Existing ${unique}`;
  13 | 
  14 |   // -- Baseline: a saved estimate with Compute Engine only -----------------
  15 |   await page.goto("/estimate/new");
  16 |   await page.getByLabel("Project name").fill(projectName);
  17 |   await page.getByText("I know exactly what I need").click();
  18 |   await page.getByLabel("Instance count").fill("2");
  19 |   await page.getByLabel("vCPU (per instance)").fill("4");
  20 |   await page.getByLabel("RAM GB (per instance)").fill("16");
  21 |   await page.getByRole("button", { name: "Generate estimate" }).click();
  22 |   await expect(page.getByText("Priced instantly")).toBeVisible({ timeout: 45_000 });
  23 | 
  24 |   await page.getByRole("button", { name: "Save to a project" }).click();
  25 |   await expect(page.getByRole("heading", { name: "Save to a project" })).toBeVisible();
  26 |   await expect(page.getByRole("button", { name: "Save estimate" })).toBeEnabled();
  27 |   await page.getByRole("button", { name: "Save estimate" }).click();
  28 |   await expect(page).toHaveURL(/\/projects\/(\d+)\/estimates\/(\d+)/, { timeout: 45_000 });
  29 |   const match = page.url().match(/\/projects\/(\d+)\/estimates\/(\d+)/);
  30 |   const projectId = match![1];
> 31 |   const baselineMonthly = await page.locator("text=/mo").first().textContent();
     |                                                                  ^ Error: locator.textContent: Test timeout of 180000ms exceeded.
  32 | 
  33 |   // -- Existing Estimate: pick this project, add only Vertex AI -----------
  34 |   await page.goto(`/estimate/existing?project=${projectId}`);
  35 |   await expect(page.getByRole("heading", { name: "Existing estimate" })).toBeVisible();
  36 | 
  37 |   // Sizing starts collapsed with an "unchanged" summary - never re-asked.
  38 |   await expect(page.getByText(/Unchanged from v1/)).toBeVisible({ timeout: 15_000 });
  39 |   await expect(page.getByLabel("Instance count")).toHaveCount(0);
  40 |   // Basics (project name) is nowhere on this page at all.
  41 |   await expect(page.getByLabel("Project name")).toHaveCount(0);
  42 | 
  43 |   await page.getByPlaceholder("Search GCP services...").fill("Vertex AI");
  44 |   const vertexCard = page.getByTestId("service-card-vertex-ai");
  45 |   await expect(vertexCard).toBeVisible();
  46 |   await vertexCard.getByRole("button", { name: "Add" }).click();
  47 |   await expect(page.getByLabel(/^Quantity for Vertex AI$/)).toBeVisible();
  48 | 
  49 |   // Still nothing but the new service and the unchanged-sizing summary -
  50 |   // no Compute Engine field, no other unrelated resource, appeared.
  51 |   await expect(page.getByLabel("vCPU (per instance)")).toHaveCount(0);
  52 | 
  53 |   await page.getByRole("button", { name: "Update existing estimate" }).click();
  54 |   await expect(page.getByText(/Updated to v2/)).toBeVisible({ timeout: 45_000 });
  55 | 
  56 |   await page.getByRole("link", { name: "View in project" }).click();
  57 |   await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/estimates/2`));
  58 |   const resourceTable = page.getByTestId("resource-summary-table");
  59 |   await expect(resourceTable.getByRole("cell", { name: /^Compute Engine/ }).first()).toBeVisible();
  60 |   await expect(resourceTable.getByRole("cell", { name: /^Vertex AI/ }).first()).toBeVisible();
  61 |   expect(baselineMonthly).toBeTruthy();
  62 | });
  63 | 
```