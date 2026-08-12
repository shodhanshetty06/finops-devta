# GCP FinOps Estimation Platform - Phases 1-6

AI-powered Google Cloud FinOps estimation engine. Phase 1 delivers the
backend core: input validation, normalization, AI recommendation,
architecture recommendation, and pricing. Phase 2 adds professional Excel
and PDF report generation. Phase 3 adds persistence, JWT authentication,
role-based access control, and versioned project/estimate history. Phase 4
adds input ingestion: an Excel questionnaire (upload or download-a-blank-
template) and free-text natural-language requirement extraction. Phase 5
adds a live pricing provider backed by the real Google Cloud Billing
Catalog API, selectable via `FINOPS_PRICING_PROVIDER=gcp` with zero changes
anywhere else in the codebase. Phase 6 adds a Next.js frontend - a
questionnaire wizard with live validation feedback, a cost dashboard with
charts and an architecture diagram, dark/light mode, and Excel/PDF export -
in `frontend/`. All of it is exposed via a documented REST API. Pricing is
always sourced from a `PricingProvider` interface (mock or live GCP - see
`docs/ROADMAP.md`), never computed ad hoc.

See `docs/ARCHITECTURE.md` for the design and `docs/ROADMAP.md` for the full
multi-phase plan (FinOps optimization features, multi-cloud, production
hardening).

## What's built

### Phase 1 - Backend Core

- **Domain models** (`backend/app/domain/`): typed schemas for customer
  requirements, validation results, assumptions, normalized specs, cost
  breakdowns, architecture recommendations, and audit logs.
- **Catalog abstraction** (`backend/app/catalog/`): a `CatalogProvider`
  interface with a mock implementation describing valid Compute Engine
  machine types, disk types, GPU types, regions, Cloud SQL tiers, and GKE
  limits.
- **Validation rule engine** (`backend/app/validation/`): 13 rules (CPU, RAM,
  machine family, GPU, region, disk, cloud storage, Cloud SQL tier, load
  balancer, network, Kubernetes, availability, backup), each returning
  requested value / supported value / reason / severity / recommendation.
- **Normalization engine** (`backend/app/normalization/`): conservative /
  balanced / performance strategies that resolve unsupported requested
  values to valid GCP configurations, logging every substitution as an
  `Assumption`.
- **AI recommendation engine** (`backend/app/services/recommendation_engine.py`):
  infers compute/database/network/Kubernetes needs from business-only input.
- **Architecture engine** (`backend/app/services/architecture_engine.py`):
  rule-based recommended architecture.
- **Pricing engine** (`backend/app/pricing/`): computes monthly/yearly/3-year
  cost, discounts, tax, and a support plan uplift - always via a
  `PricingProvider`, never hardcoded in business logic.
- **Audit logging** (`backend/app/audit/`): a complete, ordered log of every
  validation finding, assumption, and priced line item.

### Phase 2 - Report Generation

- **Excel generator**: a 13-sheet workbook (Summary, Compute, Storage,
  Database, Networking, Licensing, Assumptions, Validation, Recommendations,
  Pricing, Totals, Yearly Cost, Audit) with color-coded headers, frozen
  panes, and **live Excel formulas** - verified to recalculate correctly via
  headless LibreOffice.
- **PDF generator**: a client-ready proposal with executive summary,
  architecture, itemized pricing, charts, assumptions, validation results,
  savings opportunities, totals, and a signature block.
- Both accept a `BrandingConfig` for white-labeling.

### Phase 3 - Persistence, Auth, Projects

- **Database layer** (`backend/app/db/`): SQLAlchemy ORM models for `users`,
  `projects`, `estimate_versions`, and `audit_log_rows`. SQLite by default,
  Postgres in production. Alembic migrations (`backend/alembic/`).
- **Auth**: bcrypt password hashing, JWT bearer tokens, three roles
  (`admin`, `consultant`, `customer`).
- **RBAC**: enforced in `ProjectService` - admins can access any project,
  everyone else only their own.
- **Repository pattern** (`backend/app/repositories/`): isolates all
  SQLAlchemy query code from services.
- **Project & estimate history**: every save creates an immutable,
  auto-incrementing version - nothing is overwritten. Past versions can be
  reloaded or re-exported to Excel/PDF at any time.

### Phase 4 - Input Ingestion

- **Excel questionnaire** (`backend/app/intake/`): `GET .../template`
  downloads a blank, professionally formatted workbook (section headers,
  dropdown validation for every enum/boolean field) generated from a single
  `FIELD_SCHEMA` that also drives the parser - so template and parser can
  never drift apart. The parser tolerates bad input gracefully: one invalid
  cell produces a field-scoped `ParseIssue`, not a failed upload; a whole
  section is only dropped if it's genuinely unusable (e.g. a required field
  left blank), and every other section still comes through.
- **Natural-language extraction** (`app/intake/text_extractor.py`):
  regex/keyword rules turn free text like "500 users, HA required, 99.99%
  uptime, 100GB database" into user counts, an availability block, region,
  database, networking, and Kubernetes hints - explicitly rule-based, not a
  hosted LLM call (documented as a drop-in replacement point for one later).
  Every inference is returned as an `Assumption` with the reasoning behind
  it.
- Stateless endpoints (`/api/v1/intake/*`) mirror `/api/v1/estimate`'s
  no-persistence design, with an `auto_estimate` flag to get a priced result
  in the same call. Persisted shortcuts
  (`/api/v1/projects/{id}/intake/*`) parse/extract and save directly as a
  new project version.

### Phase 5 - Live Google Cloud Pricing

- **Cloud Billing Catalog client** (`backend/app/pricing/gcp_client.py`): a
  retrying, paginating HTTP client for the real
  `cloudbilling.googleapis.com` API, supporting either a service-account
  bearer token or a plain API key.
- **SKU matching** (`app/pricing/sku_matcher.py`): maps machine family,
  disk type, GPU type, and Cloud SQL tier to real SKU descriptions -
  filtering by category/keywords for *what* a SKU prices and by the API's
  structured `serviceRegions` field (not text-parsing) for *where* it
  applies.
- **SKU cache** (`app/pricing/cache.py`): Redis-backed with an automatic
  in-memory fallback, so a missing Redis never breaks pricing.
- **`GcpPricingProvider`** (`app/pricing/gcp_provider.py`): implements the
  same `PricingProvider` interface as the mock provider - swap it in with
  `FINOPS_PRICING_PROVIDER=gcp` plus `FINOPS_GCP_SERVICE_ACCOUNT_JSON` or
  `FINOPS_GCP_API_KEY`; nothing above the interface changes.
- **Known limitation:** the *validation* catalog (`app/catalog/`) still
  runs on mock data - only pricing was made live this phase (see
  `docs/ROADMAP.md` Phase 5 for the full scope note).
- **Live-credential status:** built and tested against realistic mocked API
  responses; a real end-to-end HTTP round-trip has not yet been run (the
  development environment has no network path to Google). See
  `docs/PHASE5_LIVE_VERIFICATION.md` for how to confirm it with a live key.

### Phase 6 - Frontend + Dashboard

- **Next.js 16 app** (`frontend/`, TypeScript, Tailwind v4, React Query) -
  see `frontend/README.md` and `docs/PHASE6_NOTES.md`.
- **Questionnaire wizard** (`frontend/src/components/wizard/`): 8 steps
  mirroring `CustomerRequirement`, a toggle between explicit sizing and
  business-context (AI-sized) mode, and live "as you type" validation via
  debounced `POST /api/v1/validate` calls.
- **Cost dashboard** (`/projects/[id]/estimates/[version]`): monthly/
  yearly/3-year totals, a cost-breakdown pie chart and projection bar chart
  (Recharts), an itemized line-item table, validation results, assumptions,
  audit log, and a Mermaid-rendered architecture diagram.
- **Dark/light mode** (next-themes) and **Excel/PDF export buttons** that
  stream the existing report endpoints through an authenticated download.
- **Projects + version history** (`/projects`, `/projects/[id]`) and both
  Phase 4 intake paths (`/projects/[id]/intake`).
- **24 Vitest tests**; `tsc --noEmit`, `eslint`, and `next build` all clean.
- **Known limitation:** full interactive browser testing (clicking through
  the live wizard, confirming the Mermaid SVG actually renders, exercising
  a real file download) wasn't automated in this pass - see
  `docs/PHASE6_NOTES.md` for a manual checklist and the Playwright
  follow-up this is tracked under.

### REST API

`POST /api/v1/validate`, `POST /api/v1/estimate`,
`POST /api/v1/reports/{excel,pdf}`, `GET /api/v1/catalog/*`,
`POST /api/v1/auth/{register,login}`, `GET /api/v1/auth/me`,
`POST/GET /api/v1/projects`, `GET /api/v1/projects/{id}`,
`POST/GET /api/v1/projects/{id}/estimates`,
`GET /api/v1/projects/{id}/estimates/{version}`,
`POST /api/v1/projects/{id}/estimates/{version}/reports/{excel,pdf}`,
`GET /api/v1/intake/excel/template`, `POST /api/v1/intake/{excel,text}`,
`POST /api/v1/projects/{id}/intake/{excel,text}`,
`GET /health` - with Swagger UI at `/docs` (the "Authorize" button works
directly against `/api/v1/auth/login`).

**144 automated tests** covering every validation rule, every normalization
strategy, pricing math, the recommendation engine, the orchestration
pipeline, Excel sheet/formula correctness, PDF structural and text-content
correctness, auth/RBAC, the full project + versioned-estimate lifecycle,
repository-layer behavior, Excel questionnaire round-tripping and malformed-
input handling, natural-language extraction (including the platform spec's
own example verbatim), the HTTP API end to end, and the live GCP pricing
client/matcher/cache/provider against realistic mocked Cloud Billing API
responses.

## Project structure

```
gcp-finops-platform/
  backend/
    app/
      core/            settings, exceptions, logging, security (hashing + JWT)
      domain/           shared Pydantic schemas (+ branding, auth, project, intake)
      catalog/           CatalogProvider interface + mock data
      validation/        13-rule validation engine
      normalization/      conservative/balanced/performance strategies
      pricing/            PricingProvider interface + mock data + PricingEngine;
                           gcp_client.py, sku_matcher.py, cache.py, gcp_provider.py (Phase 5 live pricing)
      services/           EstimationService, ArchitectureEngine, RecommendationEngine,
                           AuthService, ProjectService
      audit/              AuditLogger
      reports/             ExcelReportGenerator, PdfReportGenerator, styles
      db/                  SQLAlchemy Base, ORM models, session/get_db
      repositories/        UserRepository, ProjectRepository, EstimateVersionRepository
      intake/              FIELD_SCHEMA, ExcelTemplateGenerator, ExcelQuestionnaireParser,
                           NaturalLanguageRequirementExtractor
      api/                FastAPI routers + DI wiring
      main.py             FastAPI app
    alembic/              migrations (0001_initial_schema.py)
    scripts/              verify_gcp_pricing.py - manual live-credential check (not part of pytest)
    secrets/               local-only GCP credential storage, gitignored
    tests/                pytest suite (144 tests)
    requirements.txt
    requirements-dev.txt (adds pypdf, used only by tests)
    Dockerfile
    pytest.ini
  frontend/
    src/
      app/                Next.js routes (login, register, projects, wizard, dashboard, intake)
      components/          charts, panels, nav, wizard steps
      components/ui/        hand-built primitives (button, input, card, ...)
      contexts/             AuthProvider
      lib/                   api-client, types, utils, React Query provider
    README.md
  docs/
    ARCHITECTURE.md
    ROADMAP.md
    PHASE5_LIVE_VERIFICATION.md
    PHASE6_NOTES.md
  examples/
    sample_request_business_only.json
    sample_request_explicit_compute.json
    sample_response_estimate.json
    sample_report.xlsx
    sample_report.pdf
    sample_filled_questionnaire.xlsx
  docker-compose.yml
  README.md
```

## Running it

```bash
cd backend
pip install -r requirements-dev.txt   # or requirements.txt if you don't need to run tests
uvicorn app.main:app --reload
```

By default this uses SQLite (`finops.db`, auto-created on startup) so there's
nothing else to set up locally. Open `http://localhost:8000/docs` for
interactive Swagger docs.

Or with Docker (uses Postgres, with migrations applied via Alembic):

```bash
docker compose up -d postgres
cd backend && FINOPS_DATABASE_URL=postgresql+psycopg2://finops:finops_dev_password@localhost:5432/finops alembic upgrade head && cd ..
docker compose up backend
```

Frontend (with the backend running above):

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open `http://localhost:3000`.

## Verifying it

```bash
cd backend
pytest -q
```

Expected: `144 passed`.

```bash
cd frontend
npx tsc --noEmit && npm run lint && npm test && npm run build
```

Expected: no type errors, no lint errors, `24 passed`, and a successful
production build.

Manual smoke test (questionnaire -> priced estimate in one call):

```bash
curl -s -o questionnaire.xlsx http://localhost:8000/api/v1/intake/excel/template
# ... fill in questionnaire.xlsx in Excel ...
curl -s -X POST "http://localhost:8000/api/v1/intake/excel?auto_estimate=true" \
  -F "file=@questionnaire.xlsx" | python3 -m json.tool
```

Or natural language:

```bash
curl -s -X POST "http://localhost:8000/api/v1/intake/text?auto_estimate=true" \
  -H "Content-Type: application/json" \
  -d '{"project_name":"New Customer Portal","text":"500 users, HA required, 99.99% uptime, 100GB database"}' \
  | python3 -m json.tool
```

Auth + project history flow:

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"consultant@example.com","password":"supersecret123","full_name":"Consultant","role":"consultant"}'

TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=consultant@example.com&password=supersecret123" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

PROJECT_ID=$(curl -s -X POST http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Retail Client Migration"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

# Upload a filled questionnaire straight into project history:
curl -s -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/intake/excel" \
  -H "Authorization: Bearer $TOKEN" -F "file=@examples/sample_filled_questionnaire.xlsx" | python3 -m json.tool

# Re-export that saved version any time, without recomputing pricing:
curl -s -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/estimates/1/reports/pdf" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{}' -o v1.pdf
```

## Example: the "impossible configuration" scenario from the spec

Request: `compute.vcpu = 3` on the `e2` family (does not exist as a real
Google Cloud machine type) with `normalization_strategy = "performance"`.

Result: validation flags it as a WARNING (not a BLOCKER - it's resolvable),
normalization selects `e2-standard-4` (nearest higher, per the performance
strategy), and the response includes an `Assumption`:

```json
{
  "field": "compute.vcpu",
  "requested_value": "3",
  "used_value": "4",
  "reason": "3 vCPU configuration does not exist in the e2 family. Selected nearest higher supported value (performance strategy).",
  "strategy_applied": "performance"
}
```

This exact assumption appears in `audit_log.entries`, the Excel
**Assumptions** sheet, and the PDF **Assumptions** section - see
`examples/sample_report.xlsx` / `examples/sample_report.pdf`. It can also be
saved permanently to a project and reloaded or re-exported at any later time
(Phase 3), and `examples/sample_filled_questionnaire.xlsx` (Phase 4) shows
the same scenario entered through the Excel questionnaire path.

## Example: the natural-language extraction scenario from the spec

Input: `"500 users, HA Required, 99.99% uptime, 100GB Database"`.

The extractor detects total/peak users (500), high availability, a 99.99%
uptime target, disaster-recovery-appropriate backup frequency, and a 100 GB
Postgres database - each with an `Assumption` explaining what phrase
triggered it. With `auto_estimate=true`, this flows straight into the AI
recommendation engine (Phase 1, since no explicit compute was given) and
comes out the other end as a fully priced `EstimateResult`.

## Configuration

All settings are environment variables prefixed `FINOPS_` (see
`.env.example`), notably:

- `FINOPS_PRICING_PROVIDER` - `mock` (default) or `gcp` (Phase 5, live Cloud Billing Catalog API)
- `FINOPS_GCP_SERVICE_ACCOUNT_JSON` / `FINOPS_GCP_API_KEY` - required only when `gcp` is selected
- `FINOPS_REDIS_URL`, `FINOPS_SKU_CACHE_TTL_SECONDS` - live SKU cache (optional; falls back to in-memory)
- `FINOPS_DEFAULT_NORMALIZATION_STRATEGY` - `conservative` / `balanced` / `performance`
- `FINOPS_DEFAULT_TAX_RATE_PERCENT`, `FINOPS_SUPPORT_PLAN_PERCENT`
- `FINOPS_DATABASE_URL` - SQLite by default; Postgres connection string in production
- `FINOPS_AUTO_CREATE_TABLES` - `true` for local dev convenience; set `false` and run
  `alembic upgrade head` in any shared environment
- `FINOPS_JWT_SECRET_KEY` - **must** be overridden to a random value outside local dev

## Next phase

Phase 7 (async jobs & scale-out) is next per `docs/ROADMAP.md`, followed by
the FinOps optimization feature set and multi-cloud support - built
incrementally, each fully tested before the next starts. Two follow-ups
from earlier phases are still open: Phase 5's live pricing needs a real
end-to-end credential run outside this sandbox (`docs/PHASE5_LIVE_VERIFICATION.md`),
and Phase 6's frontend needs a manual (or Playwright-automated) browser
pass (`docs/PHASE6_NOTES.md`).
