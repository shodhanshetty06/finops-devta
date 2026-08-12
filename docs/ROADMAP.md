# Phased Delivery Roadmap

Full scope: an AI-powered Google Cloud FinOps Estimation & Pricing SaaS
platform (questionnaire/Excel intake -> validation -> normalization -> live
GCP pricing -> Excel/PDF proposals -> dashboard -> FinOps optimization
features), built with clean architecture and no placeholder/TODO code.

Each phase below ends with a working, tested increment before the next
starts, per the project's development approach.

## Phase 1 - Backend Core (COMPLETE)

**Built:** FastAPI service with domain models, GCP catalog abstraction (mock
data mirroring the real Compute Engine / Cloud SQL / GKE catalogs), a
13-rule validation engine, a 3-strategy normalization engine, a pricing
engine that always delegates to a `PricingProvider`, an AI recommendation
engine for business-only submissions, a rule-based architecture
recommendation engine, full audit logging, and REST endpoints
(`/api/v1/validate`, `/api/v1/estimate`, `/api/v1/catalog/*`, `/health`)
with Swagger docs.

**Tested:** 32 unit/integration tests covering every rule, every
normalization strategy, pricing math (discounts, tax, support, totals), the
AI recommendation engine, the full orchestration pipeline, and the HTTP API.

**Explicitly deferred:** live GCP billing integration, persistence, auth,
frontend, document generation.

## Phase 2 - Report Generation (Excel + PDF) (COMPLETE)

**Built:** `ExcelReportGenerator` (openpyxl) producing all 13 required
sheets - Summary, Compute, Storage, Database, Networking, Licensing,
Assumptions, Validation, Recommendations, Pricing, Totals, Yearly Cost,
Audit - with color-coded headers, frozen panes, zebra/severity highlighting,
and **live Excel formulas** (subtotals are `=SUM(...)` ranges, Totals pulls
from Pricing via `=Pricing!G12`, Yearly Cost pulls from Totals via
`=Totals!B9`, monthly x12/x36) rather than pre-baked numbers - verified by
recalculating the generated workbook with headless LibreOffice and
confirming the recalculated totals match the API's numbers exactly.
`PdfReportGenerator` (reportlab) producing a client-ready proposal: cover +
executive summary, recommended architecture table, itemized pricing table,
a cost-breakdown pie chart and monthly/yearly/3-year bar chart, assumptions,
severity-color-coded validation results, savings opportunities &
optimization recommendations (derived from applied discounts and
warning/blocker recommendations), totals, and a signature/approval block.
Both generators take a `BrandingConfig` (company name, prepared by/for,
contact email, accent color, footer note) so output can be white-labeled.
New endpoints: `POST /api/v1/reports/excel`, `POST /api/v1/reports/pdf` -
both accept a `ReportRequest` (an already-computed `EstimateResult` plus
optional branding) and stream back a downloadable file. Reports never
recompute pricing; they only render what `/api/v1/estimate` already
returned, so an exported file can never disagree with the on-screen numbers.

**Tested:** 10 new tests (42 total) - Excel sheet presence/content, formula
presence (not hardcoded numbers), PDF structural validity (`pypdf` text
extraction) confirming every section, architecture component, and the exact
total cost figure appear in the rendered PDF, and end-to-end API tests
confirming correct `Content-Type`/`Content-Disposition` and file signatures
(`PK` for xlsx, `%PDF-` for pdf).

**Explicitly deferred:** logo image embedding (currently text-only
branding), multi-currency rendering, chart types beyond pie/bar, persistence
of generated reports (Phase 3 will let these be saved/retrieved by project).

## Phase 3 - Persistence, Auth, Projects (COMPLETE)

**Built:** SQLAlchemy ORM schema (`app/db/models.py`) - `users`, `projects`,
`estimate_versions`, and `audit_log_rows` (the audit trail expanded into
queryable rows, not just a JSON blob) - with an Alembic initial migration
(`alembic/versions/0001_initial_schema.py`, verified to apply cleanly to a
fresh database) and SQLite-by-default / Postgres-in-production configuration
(`FINOPS_DATABASE_URL`, wired into `docker-compose.yml`). JWT auth
(`app/core/security.py`, bcrypt password hashing + PyJWT tokens) with
role-based access control across three roles - `admin`, `consultant`,
`customer` - enforced in `ProjectService`: admins can access any project,
everyone else only their own. A repository layer
(`app/repositories/{user,project,estimate}_repository.py`) isolates all
SQLAlchemy query code from services, per the clean-architecture repository
pattern. New endpoints: `POST/GET /api/v1/auth/{register,login,me}` and the
full project lifecycle under `/api/v1/projects` - create, list, get, and
crucially `POST .../estimates` which runs Phase 1's `EstimationService` and
persists the result as an immutable, auto-incrementing version (nothing is
ever overwritten), plus `GET .../estimates` (history) and
`GET .../estimates/{version}` (reload a past estimate exactly as computed).
Two more endpoints reuse Phase 2's generators to export any saved version to
Excel/PDF on demand, closing the loop between persistence and reporting.

**Tested:** 19 new tests (61 total) - registration/login/RBAC at the API
level (401 unauthenticated, 403 cross-user, 409 duplicate email), full
project + versioned-estimate lifecycle through the HTTP API, saved-version
report export, and repository-layer tests exercised directly against a
`Session` (no HTTP) to prove the repository pattern independent of FastAPI.
Verified end-to-end against a live server with `alembic upgrade head` run
against a fresh database first (the production-style flow, not just
dev-convenience auto-create-tables).

**Known scope limitation:** registration currently allows self-assigning any
role, including `admin` - acceptable for this internal/demo phase, but a
real deployment should restrict admin creation to an existing admin or a
seed script (tracked for Phase 10 hardening). Project sharing/collaboration
(e.g. a consultant managing a customer's project) is not yet implemented -
ownership is single-user only.

## Phase 4 - Input Ingestion (COMPLETE)

**Built:** A single `FIELD_SCHEMA` (`app/intake/schema.py`) drives both a
downloadable blank Excel questionnaire (`ExcelTemplateGenerator` - section
headers, dropdown data validation for every enum/boolean field, an example
column) and the parser that reads a filled-in copy back
(`ExcelQuestionnaireParser`), so the two can never drift apart. The parser
never fails the whole upload for one bad cell: an invalid enum value or a
missing required field is reported as a `ParseIssue` scoped to that field or
section, and every other section still comes through - verified with a
template round-trip test and a deliberately-broken-cells test. A second
extractor, `NaturalLanguageRequirementExtractor`
(`app/intake/text_extractor.py`), turns free-text business requirements
(e.g. "500 users, HA required, 99.99% uptime, 100GB database" - the exact
example from the platform spec) into user counts, an availability block,
region, database, networking, and Kubernetes hints via regex/keyword rules -
explicitly NOT a hosted LLM call, and documented as a drop-in replacement
point for one later. Every inference from both paths is returned as an
`Assumption`, the same transparency model the normalization engine uses.
New endpoints: `GET /api/v1/intake/excel/template`,
`POST /api/v1/intake/{excel,text}` (stateless, optional `auto_estimate` to
also return a priced `EstimateResult` in one call), and persisted shortcuts
`POST /api/v1/projects/{id}/intake/{excel,text}` that parse/extract and save
directly as a new project version, reusing Phase 3's versioning.

**Tested:** 26 new tests (87 total) - a schema-uniqueness invariant test (a
regression guard: two fields sharing a label would silently corrupt parsing,
which is exactly the bug this test caught during development - see below),
full round-trip and malformed-input tests for the Excel path, extraction
tests for the NL path including the spec's own example verbatim, and
API-level tests for all five endpoints including the persisted shortcuts.
Verified end-to-end on a live server: downloaded the real template, filled
it in with openpyxl exactly as a user would in Excel, uploaded it with
`auto_estimate=true`, and got back a correctly priced estimate.

**Bug caught during development:** the first schema draft had "vCPU",
"RAM (GB)", "Required", "High Availability", and "Size (GB)" each appearing
in two different sections (e.g. Compute and Database) with identical label
text. Because the parser matches by label text rather than sheet position,
the second occurrence of each silently overwrote the first, and Database/
Kubernetes fields never parsed even though the cells were filled in
correctly. Fixed by making every label globally unique (e.g. "Database
vCPU") and adding a test that asserts `FIELD_SCHEMA` never has duplicate
labels, so this class of bug can't reappear silently in a future edit.

**Explicitly deferred:** GPU/ML workload detection in the NL extractor
surfaces as an explanatory note but does not auto-provision GPU-enabled
compute (would require extending the AI recommendation engine to reason
about accelerators); CSV/other spreadsheet formats beyond .xlsx; OCR or
PDF-based intake.

## Phase 5 - Live Google Cloud Pricing Integration (COMPLETE, pending live-credential verification)

**Built:** `CloudBillingCatalogClient` (`app/pricing/gcp_client.py`) - a
retrying, paginating HTTP client for the real
`cloudbilling.googleapis.com/v1` Catalog API, supporting both auth modes
Google offers for it: a service account bearer token (via `google-auth`) or
a plain restricted API key. Retries with exponential backoff on 429/5xx
only; anything else (401/403/404) fails immediately since a retry can't fix
a configuration problem. A `SkuCache` (`app/pricing/cache.py`) avoids
re-fetching a service's full SKU list (10,000+ rows for Compute Engine
alone) on every price lookup - Redis-backed when reachable, with an
automatic in-memory fallback so a missing Redis never breaks pricing, only
loses cross-process sharing. `sku_matcher.py` maps this platform's pricing
concepts (machine family, disk type, GPU type, Cloud SQL tier) to real SKU
descriptions, splitting the problem into two independently-verifiable
steps: keyword/category filtering identifies *what* a SKU prices, and the
API's structured `serviceRegions` field (not text-parsing) identifies
*where* it applies. `GcpPricingProvider` (`app/pricing/gcp_provider.py`)
composes these into the exact same `PricingProvider` interface
`MockGCPPricingProvider` implements - `PricingEngine` and everything above
it needs zero changes to use it. Currency conversion is delegated to
Google itself (SKUs are requested directly in `FINOPS_DEFAULT_CURRENCY` via
the API's `currencyCode` parameter) rather than maintaining a separate
FX-rate feed. Cutover is a single setting: `FINOPS_PRICING_PROVIDER=gcp`
plus one of `FINOPS_GCP_SERVICE_ACCOUNT_JSON` / `FINOPS_GCP_API_KEY`.

**Tested:** 57 new tests (144 total) - the HTTP client against a fake
transport shaped exactly like Google's documented response schema
(pagination, both auth modes, retry-then-succeed, retry-exhaustion,
non-retryable errors), the SKU matcher against hand-built fixtures that
include deliberate decoys (wrong region, preemptible, custom-machine-type
variants, wrong resource family) to prove the correct SKU wins over
plausible near-misses, the cache (TTL expiry, Redis-unreachable fallback),
and `GcpPricingProvider` end-to-end across all fourteen `PricingProvider`
methods with hand-calculated expected prices, including a caching-behavior
test confirming repeated lookups against the same service make no
additional HTTP calls.

**Explicitly deferred / known limitation:** `GcpCatalogProvider` (a live
version of the *validation* catalog - "is region X / machine family Y
supported") was not built this phase; validation still runs against the
mock catalog, which already mirrors the real supported-value sets closely
enough for validation purposes. Sustained/committed-use discounts reuse the
same flat, publicly-advertised percentages the mock provider uses rather
than resolving Google's separate per-family commitment SKUs (tracked under
Phase 8's Reserved Instance / Committed Use recommendation engine).
Multi-tier volume pricing beyond a SKU's first tier is not modeled.

**Live-credential verification status: DONE (2026-08-12).** Run from a
machine with real internet access via `python -m scripts.verify_gcp_pricing`,
all 7 representative lookups succeeded end-to-end (Google auth -> Cloud
Billing Catalog API -> SKU matching -> pricing math). Two SKU-matching
keyword mismatches were found and fixed (network egress, GKE cluster
management fee - Google's real SKU descriptions differed from the
documented-convention assumption `sku_matcher.py` was built against); full
details in `docs/PHASE5_LIVE_VERIFICATION.md`. No structural code changes
were needed - exactly as predicted, only two keyword/fixture updates.

## Phase 6 - Frontend + Dashboard (COMPLETE)

**Built:** a Next.js 16 (App Router, TypeScript, Tailwind v4) frontend in
`frontend/` talking to every Phase 1-5 endpoint through one typed client
(`src/lib/api-client.ts` - one function per backend route, so an endpoint
change only needs an edit in one place). Auth (`src/contexts/auth-context.tsx`)
persists a JWT in `localStorage` and attaches it via an axios interceptor
that also handles 401s. A hand-built UI primitive set (`src/components/ui/`
- button, input, select, card, badge, progress, etc., styled with
`class-variance-authority` + Tailwind, in the shadcn/ui style) backs
everything; React Query (`@tanstack/react-query`) owns server-state caching
for projects/estimates.

The questionnaire wizard (`src/components/wizard/`) mirrors
`CustomerRequirement` section-for-section (basics, sizing, storage,
database, network, Kubernetes, availability, review) with a toggle between
"I know exactly what I need" (explicit compute spec) and "size it for me"
(business context - triggers the backend's AI recommendation engine, same
as the Phase 1/4 spec examples). Every field change debounces a call to
`POST /api/v1/validate` and renders the live, severity-coded result inline
- this is the "as you type" validation feedback, not just a post-submit
error list. The estimate dashboard (`/projects/[id]/estimates/[version]`)
renders monthly/yearly/3-year totals, a cost-breakdown pie chart and a
projection bar chart (Recharts), an itemized line-item table with discounts/
tax/support/total, the full validation report, every assumption made, the
audit log, and a Mermaid-rendered architecture diagram built from the
backend's ordered component list. Dark/light mode is `next-themes` wired to
a Tailwind v4 custom `dark` variant; Excel/PDF export buttons stream the
existing report endpoints through an authenticated blob download (a plain
`<a href>` can't carry the Authorization header these endpoints require).
Projects (`/projects`) and per-project version history
(`/projects/[id]`) round out the persistence-backed flow from Phase 3, and
`/projects/[id]/intake` exposes both Phase 4 ingestion paths (Excel
questionnaire upload, free-text extraction).

**Tested:** 24 Vitest + React Testing Library tests - currency/date/severity
formatting utilities, API error-message extraction across the backend's
error response shapes, the wizard's state machine (section toggles, sizing
mode switching, step bounds), and the validation panel's
severity-ordering/counting logic. `npx tsc --noEmit` and `eslint` both run
clean, and `next build` produces a working production build (verified by
serving it and confirming `/`, `/login`, `/register`, and `/projects` all
return `200` with the expected content). Deeper interaction testing
(clicking through the actual wizard in a real browser end-to-end) was not
done in this pass - `docs/PHASE6_NOTES.md` has a manual verification
checklist and notes Playwright as the natural next step for automating it.

**Explicitly deferred:** true shadcn/ui CLI-managed components (the
hand-built primitives cover the same visual language without pulling in
Radix - a pragmatic substitution, not a missing feature); a components-only
Storybook; offline/PWA support; CSV export in addition to Excel/PDF.

## Phase 7 - Async Jobs & Scale-Out (COMPLETE)

**Built:** a Celery app (`app/tasks/celery_app.py`) using Redis as both
broker and result backend (the same Redis Phase 5's SKU cache uses).
`generate_report_task` (`app/tasks/report_tasks.py`) runs Excel/PDF
generation - the platform's heaviest single-request CPU cost - off the
request thread, returning the file base64-encoded in the task result.
`generate_batch_estimates_task` (`app/tasks/batch_tasks.py`) prices a list
of `CustomerRequirement`s in one job, pricing each independently so one bad
item never fails the whole batch (the same per-item-isolation philosophy
the Phase 4 intake parser uses). New endpoints under `/api/v1/jobs/*`:
`POST .../reports` and `POST .../batch-estimate` enqueue and return a job
id immediately (202), `GET .../{job_id}` polls status/result, and
`GET .../{job_id}/download` streams a finished report job's file. A
`celery-worker` service in `docker-compose.yml` runs the actual workers;
without it, jobs are accepted and queued but stay `PENDING` until a worker
picks them up.

Rate limiting (`app/middleware/rate_limit.py`) is a fixed-window counter
per client IP, Redis-backed with the same automatic in-memory fallback
pattern as the SKU cache - "heavy" endpoints (estimate/report/job/intake
generation) get a stricter per-minute limit than everything else, since
one of those costs far more CPU than a catalog lookup. Structured request
logging (`app/middleware/request_logging.py`) emits one JSON log line per
request (method, path, status, duration, client IP, request id) and
returns the request id via an `X-Request-ID` header, so a reported issue
can be grepped straight to its server-side log line. Secrets hardening
(`app/core/secrets.py`, `Settings._load_secret_files`) adds the standard
Docker/Kubernetes "secret as a mounted file" pattern
(`FINOPS_JWT_SECRET_KEY_FILE` overrides `FINOPS_JWT_SECRET_KEY`) and a
startup guard that refuses to boot with `FINOPS_ENVIRONMENT=production`
if the JWT secret is still the known-insecure default, CORS is wide open,
or auto-managed schema creation is left on - verified live by actually
attempting a production-mode startup and confirming it raises rather than
just unit-testing the check function in isolation.

**Tested:** 33 new tests (177 total) - the Celery tasks directly (in eager
mode, round-tripping through the real JSON serializer, so a task whose
arguments/return value aren't actually JSON-safe would fail here, not just
in production), the full jobs API (enqueue -> poll -> download, including
the batch task's per-item failure isolation), rate limiting (per-bucket
limits, the 429 response shape, `/health`'s exemption, independent bucket
counters), request logging (the `X-Request-ID` header, the JSON log line's
shape, correct status codes on both success and error responses), and
secrets management (file-based secret loading and all three production
startup guards, individually and combined).

**Explicitly deferred:** task result storage is Celery's own result
backend (Redis) rather than a dedicated `jobs` database table - simpler,
and consistent with treating Redis as this platform's one piece of
shared/ephemeral infrastructure, but it does mean job history isn't
queryable/listable the way project estimate versions are; Celery Beat
(scheduled/periodic tasks) and Flower (a worker monitoring UI) weren't
added since nothing in this platform yet needs a recurring job.

## Phase 8 - FinOps Optimization Features (COMPLETE)

**Built:** six engines under `app/optimization/`, all reusing
`EstimationService`/`PricingProvider` for every dollar figure rather than
computing a price independently - the same invariant every prior phase has
held. `RightsizingEngine` takes a customer-supplied `UsageMetrics` (avg/peak
CPU, optional avg RAM, observation window - this platform has no live Cloud
Monitoring integration, so utilization is an explicit input, never
inferred) and recommends downsize/upsize/terminate-idle/no-change against a
documented ~65%-peak-utilization sizing target, then re-prices the resized
spec through the real pipeline for a genuine before/after comparison.
`CommitmentEngine` evaluates 1-year and 3-year Committed Use Discounts
(reusing `PricingProvider.get_committed_use_discount_percent`, the same
method `/api/v1/estimate?commitment_term_years=` already calls) against a
workload-stability input (steady/variable) and recommends a term or
on-demand. `ForecastEngine` is pure compounding math over an
already-priced monthly total with a customer-supplied growth-rate
assumption. `CarbonEngine` estimates monthly kgCO2e from provisioned
vCPU-hours using an explicitly-labeled illustrative regional grid-intensity
table and a published-order-of-magnitude watts-per-vCPU figure - documented
as directional, not an audited carbon accounting number, since this
platform has no live emissions-factor API integration.
`RegionComparisonEngine`/`ScenarioComparisonEngine` (`comparison_engine.py`)
re-run the same requirement (with a swapped region, or a named
`overrides` patch merged one level deep) through the real pipeline once per
option and diff the results - "historical pricing comparison" from the
original scope is reinterpreted here as comparing two already-*saved*
project estimate versions (see below), since the platform has no live
time-series pricing feed to compare against.

New endpoints under `/api/v1/optimization/*`: `rightsizing`,
`commitment-recommendation`, `forecast`, `carbon`, `compare-regions`,
`compare-scenarios` - all authenticated, stateless (not tied to a saved
project). Project-level additions: `monthly_budget_usd` on `projects`
(migration `alembic/versions/0002_add_project_budget.py`, verified with a
real `alembic upgrade head` / `downgrade -1` round trip against a fresh
SQLite file, not just checked structurally), `PATCH
/api/v1/projects/{id}/budget` to set or clear it, a `budget_status`
(`within_budget`/`overage_amount`/`overage_percent`) surfaced automatically
on every new estimate version once a budget is set, and
`GET /api/v1/projects/{id}/estimates/compare?from=X&to=Y` diffing two saved
versions' totals and per-category (Compute/Storage/Database/Network/GPU)
costs.

**Tested:** 33 new tests (210 total) - each engine unit-tested directly
against the mock catalog/pricing provider (idle/downsize/upsize/no-change
rightsizing branches, steady-vs-variable commitment recommendations
including a zero-discountable-spend edge case, compounding forecast math,
carbon scaling with vCPU count and region, region/scenario comparison
including invalid-region and invalid-override error paths), API-level
tests for all six optimization endpoints plus authentication enforcement,
budget set/clear/ownership-check/overage-detection tests, a version
comparison test, and a migration-chain test that both statically checks
the Alembic revision graph has a single head and (separately, at the shell
level during verification) actually ran `alembic upgrade head` then
`downgrade -1` against a throwaway SQLite database and confirmed the
`monthly_budget_usd` column appeared and disappeared correctly.

**Explicitly deferred / known limitations:** rightsizing only evaluates the
primary compute line item (Cloud SQL and GKE node rightsizing would need
their own utilization inputs and sizing heuristics - a natural follow-up,
not built this phase); the CUD recommendation models only GCP's
resource-based flat-rate discount (matching `PricingEngine`'s existing
implementation), not the real "all upfront/partial upfront" payment options
or a cash-flow breakeven calculation; carbon figures are illustrative
(clearly labeled in every response's `methodology_note`), not sourced from
a real emissions-factor API; `compare-scenarios`' override merge is one
level deep per top-level requirement section (covers every realistic use
case - swap a whole section, or tweak the region - without a full
JSON-patch engine).

## Phase 9 - Multi-Cloud Extensibility (COMPLETE)

**Built:** `AwsCatalogProvider`/`AwsPricingProvider`
(`app/catalog/aws_provider.py`, `app/pricing/aws_provider.py`) and
`AzureCatalogProvider`/`AzurePricingProvider` (`azure_provider.py`
equivalents), implementing the exact same `CatalogProvider`/`PricingProvider`
interfaces `MockCatalogProvider`/`MockGCPPricingProvider` do - same status as
the GCP mock providers before Phase 5 (mock-only, no live AWS Pricing/Azure
Retail Prices API integration this phase). The key design decision: `Region`
and `MachineFamily` (defined once, GCP-shaped, in `app/domain/enums.py`) are
treated as a **cloud-agnostic canonical vocabulary** rather than being
GCP-specific - requesting family `"e2"` or region `"us-central1"` against the
AWS provider resolves to AWS's real T3 instance family and us-east-2 region
respectively (region/family mapping tables are documented in each provider's
module docstring and `*_mock_data.py`). GPU chip names
(`nvidia-tesla-t4`/`nvidia-l4`/`nvidia-tesla-a100`/`nvidia-tesla-v100`) and
database engine names (`postgres`/`mysql`/`sqlserver`) needed no mapping at
all - they're already real, cloud-agnostic identifiers. This design means
`CustomerRequirement`, every validation rule, `NormalizationEngine`, and
`PricingEngine` needed **zero changes** to support AWS/Azure - only the
active catalog/pricing provider changes what a canonical code *resolves to*.
Selectable via `FINOPS_CLOUD_PROVIDER=gcp|aws|azure` (default `gcp`,
preserving every prior phase's behavior exactly, including the
`FINOPS_PRICING_PROVIDER` mock/live toggle).

New cross-cloud comparison: `POST /api/v1/optimization/compare-clouds`
(`app/optimization/cloud_comparison_engine.py`) prices one requirement
against GCP, AWS, and Azure's own provider pairs directly (independent of
the server's active `FINOPS_CLOUD_PROVIDER`, so a comparison run is always
deterministic/offline) and returns cheapest/most-expensive/max-savings,
reusing `EstimationService` per cloud - never computing a price itself, the
same invariant every comparison engine in this platform holds.

**Bug fix found and fixed during this phase:** `PricingEngine.calculate()`
used to derive the pricing lookup family by parsing `machine_type.split("-")[0]`
- this only works for GCP's hyphenated `family-tier-size` naming convention
(`"e2-standard-4"` -> `"e2"`) and silently breaks for AWS's dotted
(`"m5.xlarge"`) or Azure's underscored (`"Standard_D4s_v5"`) instance names,
both of which have no hyphen to split on. Fixed by adding a `family` field to
`NormalizedSpec`, populated by `NormalizationEngine` from
`requirement.compute.machine_family.value` (the canonical code) rather than
re-derived from the resolved display name; `PricingEngine` now reads
`spec.family` directly, falling back to the old parsing behavior only for
`family=None` (e.g. a pre-Phase-9 saved estimate reloaded from the
database). Caught by the very first end-to-end AWS/Azure estimate test written
this phase - a genuine example of why "reuse the real pipeline" testing
(rather than only unit-testing each provider in isolation) matters.

A second, unrelated latent bug was also fixed in passing:
`app/catalog/dependency.py` used to gate catalog-provider resolution on
`FINOPS_PRICING_PROVIDER=="gcp"` and raise `NotImplementedError` in that
case - meaning enabling Phase 5's live GCP pricing would have broken catalog
resolution entirely in a real deployment (never caught before because no
test exercised the live-pricing path through the full DI chain). Catalog
selection is now driven by `FINOPS_CLOUD_PROVIDER` independently of the
mock/live pricing toggle, with a regression test added
(`test_cloud_provider_selection.py::test_gcp_pricing_provider_gcp_no_longer_breaks_catalog_resolution`).

**Tested:** 40 new tests (250 total) - AWS/Azure catalog and pricing
providers exercised directly (family/region/disk/GPU lookups, canonical vs.
real-name key contracts, no-sustained-use-discount-but-has-CUD pricing
behavior), `FINOPS_CLOUD_PROVIDER` dependency-injection routing for all
three values plus the two bug-fix regressions above, full end-to-end
`/api/v1/estimate` runs under `FINOPS_CLOUD_PROVIDER=aws` and `=azure`
(not just provider-level unit tests) confirming real AWS/Azure instance
names and provider-tagged cost line items come back correctly, and the
cross-cloud comparison engine/endpoint (three-way comparison, subset
selection, unsupported-cloud error handling, auth enforcement).

**Explicitly deferred / known limitations:** no live AWS Pricing API or
Azure Retail Prices API integration (mock only, same status GCP had before
Phase 5 - a natural Phase 9.x follow-up); disk type size limits are kept
identical across all three clouds for behavioral consistency rather than
matching each cloud's real per-tier min/max (e.g. real AWS st1 has a 125 GB
minimum) - documented as a simplification favoring comparability over
provisioning-limit fidelity; the carbon footprint estimator (Phase 8) does
not yet differentiate datacenter PUE by cloud provider; GKE/EKS/AKS
Autopilot-equivalent availability is assumed rather than looked up (both
EKS Fargate and AKS virtual nodes exist, so this is a reasonable default,
not a fabrication).

## Phase 10 - Production Hardening (COMPLETE)

Five workstreams: CI/CD, a real-HTTP integration test suite, load testing,
a security review, and a Kubernetes deployment guide. 256 backend unit
tests pass (up from 250 in Phase 9 - 6 new: 2 in `test_secrets.py`, 3 in
the new `test_upload_limits.py`, 1 new in `test_rate_limit.py`), plus a
separate 2-test integration suite (`tests_integration/`, deliberately
excluded from the default `pytest -q` run - see below).

**CI/CD** (`.github/workflows/ci.yml`, GitHub Actions): six jobs -
`backend-tests` (the 256-test suite + an Alembic upgrade/downgrade round-
trip check), `integration-tests` (the real-HTTP suite below, against a
real Postgres service container), `backend-security` (`pip-audit` +
`bandit`, non-blocking), `frontend-checks` (typecheck/lint/unit tests/
production build), `frontend-security` (`npm audit`, non-blocking), and
`docker-build` (confirms `backend/Dockerfile` builds). Sandbox-specific
notes preserved as inline comments in the workflow file itself: the
frontend install step uses `npm install` rather than `npm ci` because this
dependency tree's `eslint` 9 -> `ajv` peer resolution was observed to
resolve slightly differently across repeated installs in the dev sandbox
(not a real project issue - `npm audit` showed 0 vulnerabilities either
way); type checking uses an explicit `npm run typecheck` script rather than
`npx tsc` because `npx` resolved to an unrelated squatted `tsc` package in
that same sandbox.

**Integration test suite** (`backend/tests_integration/`, see its own
`README.md`): distinct from the main suite's in-process `TestClient` -
these launch a real `uvicorn` subprocess and talk to it over real HTTP
(`httpx`), walking one continuous session through most of the platform
(register -> login -> Excel intake -> project -> estimate -> every Phase 8
optimization endpoint -> Phase 9 cross-cloud comparison -> budget -> a
second estimate version -> version comparison -> Excel/PDF export -> an
async report job polled to completion -> RBAC cross-user check). Runs
against both a throwaway SQLite file (always) and a real Postgres (skipped
locally unless `FINOPS_TEST_POSTGRES_URL` is set; the CI `integration-tests`
job sets it against a real Postgres service container on every push, so the
Postgres-dialect path is genuinely exercised, not just documented).
Deliberately not part of `pytest -q` (`pytest.ini`'s `testpaths = tests`
excludes it) since it's slower - run explicitly with `pytest
tests_integration -v`.

*Bug found while building this*: the dev sandbox sets a SOCKS proxy
environment variable (for its own network-egress allowlisting) that
`httpx`'s default `trust_env=True` picked up and tried to apply even to
`127.0.0.1` requests, breaking the very first test run with `ImportError:
Using SOCKS proxy, but the 'socksio' package is not installed`. Fixed by
passing `trust_env=False` on both HTTP clients in
`tests_integration/conftest.py` and `tests_integration/test_full_user_journey.py`
- they only ever talk to a subprocess on localhost, so bypassing
environment proxy detection is correct there regardless of environment.

**Load testing** (`backend/loadtest/locustfile.py`, results recorded in
`docs/LOAD_TEST_RESULTS.md`): a [Locust](https://locust.io) scenario mixing
anonymous `/api/v1/estimate` calls (the dominant traffic pattern) with a
registered-user journey (register -> project -> estimate versions ->
`compare-clouds`, the most CPU-expensive single endpoint). 30 concurrent
users sustained for 45s against a single `uvicorn` worker on the 2-vCPU
sandbox: 914 requests, **zero failures**, 23ms median / 130ms p95 / 180ms
p99 aggregate latency, ~20.7 req/s throughput. `docs/LOAD_TEST_RESULTS.md`
is explicit that these are a *relative regression baseline* for this
codebase, not a production capacity figure - the run used SQLite (not the
production Postgres), a single process (no `gunicorn` workers), and
`FINOPS_BCRYPT_ROUNDS=4` (vs. the production-enforced minimum of 10).

*Bug found while building this*: the first run showed 133/133 requests to
`compare-clouds` failing with `401 Unauthorized` - not an app bug, a test-
script bug. Every `/api/v1/optimization/*` route requires auth
(`Depends(get_current_user)`, confirmed by reading
`app/api/routers/optimization.py`), and the scenario had that call under
the anonymous user class. Fixed by moving it to the authenticated
`RegisteredUserJourney` class; the re-run came back with zero failures.

**Security review** (`docs/SECURITY_REVIEW.md`): a genuine, tested
dependency upgrade (fastapi 0.115.6 -> 0.141.1, pyjwt -> 2.13.0, pypdf ->
6.14.2, python-multipart -> 0.0.31, pytest -> 9.0.3) resolving 33 CVEs
`pip-audit` had flagged, verified with a full test run in an isolated venv
before and after applying; two new `validate_production_security()`
(`app/core/secrets.py`) checks - JWT secret minimum length (32 chars) and a
production minimum for `FINOPS_BCRYPT_ROUNDS` (10), closing gaps the
existing exact-default-match/CORS/auto-create-tables checks didn't cover;
and a genuine unauthenticated DoS fix found by manual code review (grepping
for `UploadFile`/`await file.read()`, not caught by any automated tool) -
Excel questionnaire uploads had no size cap, so `read_upload_bounded`
(`app/core/uploads.py`) now enforces `FINOPS_MAX_UPLOAD_SIZE_BYTES` (10MB
default) on both upload endpoints, and `/api/v1/auth/login` was added to
the rate limiter's "heavy" (brute-force-sensitive) bucket alongside the
already-covered CPU-expensive endpoints. Full write-up, including reviewed-
but-no-issue-found areas (SQL injection, RBAC, CORS, CSRF, audit trail) and
accepted known limitations (self-assignable admin role, non-revocable JWT,
no app-level security headers - recommended at the ingress layer instead),
lives in `docs/SECURITY_REVIEW.md`.

**Kubernetes deployment guide** (`k8s/`, `docs/DEPLOYMENT.md`): manifests
for the full stack - `namespace`, `configmap` (non-secret config, matches
what `validate_production_security()` requires), `secret.yaml.example`
(template only, real file gitignored), a Postgres `StatefulSet` + headless
`Service`, a Redis `Deployment` + `Service`, a run-once `migration-job`
(Alembic, since `FINOPS_AUTO_CREATE_TABLES=false` in production), the
backend `Deployment` + `Service` + `HorizontalPodAutoscaler` +
`PodDisruptionBudget` (with a hardened `securityContext` -
`readOnlyRootFilesystem: true` plus a mounted `/tmp` `emptyDir`, since
FastAPI's multipart parser can spill large uploads to disk before
`read_upload_bounded` ever sees them), the `celery-worker` `Deployment`,
and an `Ingress`. `docs/DEPLOYMENT.md` walks through the full ordered
sequence (build/push image -> create Secret -> apply base stack -> run
migration Job -> roll out app -> verify) plus what's deliberately out of
scope (frontend deployment - no Dockerfile yet, better suited to static
hosting; managed Postgres/Redis as a drop-in swap; capacity planning beyond
the Phase 10 load test baseline).

**Explicitly deferred / known limitations:** Docker images were built and
tested locally but never pushed to a real registry or applied to a real
cluster (no `docker`/`kubectl` binaries in the dev sandbox - every manifest
was syntax-validated with `yaml.safe_load_all`, not `kubectl apply --dry-run`);
the frontend has no `Dockerfile` or Kubernetes manifest yet (documented in
`docs/DEPLOYMENT.md` as a recommended-static-hosting gap, not silently
missing); load test numbers are a sandboxed relative baseline as described
above, not a production capacity plan; the self-assignable-admin-role and
non-revocable-JWT limitations noted in Phase 3 remain accepted, not fixed,
per `docs/SECURITY_REVIEW.md`.
