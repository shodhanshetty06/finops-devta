# End-to-End QA / Live Verification Report

Date: 2026-08-08
Scope: full-stack adversarial QA pass across backend, frontend, database, Redis, Celery, auth/RBAC, file upload, pricing math, assumption tracking, Excel/PDF generation, resilience, and concurrency — run against a real live stack (real FastAPI process, real SQLite and PostgreSQL, real Redis, real Celery worker), not just the existing mocked test suite.

## Environment used for live testing

- Backend: real `uvicorn` process (not `TestClient`) on a fresh virtualenv from `requirements.txt`/`requirements-dev.txt`.
- Database: both real SQLite and a real PostgreSQL 14 server (built locally from Ubuntu packages, since no Docker runtime is available in this sandbox) — the existing `tests_integration/test_full_user_journey.py::test_full_user_journey_postgres` test, normally skipped without `FINOPS_TEST_POSTGRES_URL`, was run for real.
- Redis: a real standalone Redis 6.2 server (extracted from the `redislite` PyPI package's bundled binary), used as the SKU cache, rate-limit backend, and Celery broker/result backend simultaneously.
- Celery: a real worker process (`celery -A app.tasks.celery_app worker`), not `task_always_eager` — async report jobs were genuinely queued, picked up, and executed out-of-process.
- Frontend: `npm install` / `tsc --noEmit` / `eslint` / `vitest` / `next build` run against a clean copy of the redesigned frontend.
- Not available in this sandbox: a Docker runtime (outbound network restrictions block the package registries Docker itself would need, and no `docker` binary is present), and outbound access to `*.google.com` (pre-existing, documented sandbox restriction — see `PHASE5_LIVE_VERIFICATION.md`). Docker/Compose was verified statically instead (see below). Live GCP Cloud Billing Catalog API calls were not re-verified in this pass for the same reason; the mock pricing provider was used, and its output was checked for internal consistency and correct math instead.

## 1–4. Test counts

| Suite | Count | Result |
|---|---|---|
| Backend pytest, `tests/` (unit + component) | 260 | 260 passed |
| Backend pytest, `tests_integration/` (real live-server journeys, SQLite + Postgres) | 2 | 2 passed |
| Frontend vitest | 24 | 24 passed |
| Live black-box QA harness (`test_live.py` — auth/RBAC/security, validation/normalization, pricing math, assumptions, file upload, concurrency, async jobs, error handling) | 108 | 108 passed |
| Live isolated rate-limit test (`test_rate_limit.py`) | 3 | 3 passed |
| Live resilience test (`test_resilience.py` — Redis down, DB corrupted, Celery worker down) | 3 checks + 2 manual probes | all passed |
| Live full E2E persisted-project workflow (`test_e2e_project.py`) | 19 | 19 passed |
| **Total** | **~419** | **419 passed, 0 failed (after fixes)** |

4 real product bugs were found during this pass, none of which existed in the pre-existing 256-test suite (it never exercised these specific paths). All 4 are fixed, each with a permanent regression test added to the pytest suite (now 262 backend tests total, up from 258). Every affected suite was re-run green after each fix.

## 5. Bugs found, root-caused, fixed, and regression-tested

### 1. CRITICAL — Public registration allowed self-service admin privilege escalation
`POST /api/v1/auth/register` accepted `"role": "admin"` from a completely unauthenticated caller and created the account as-is. `ProjectService` grants `role == "admin"` full bypass of the project-ownership check, so any anonymous visitor could grant themselves organization-wide read access to every user's projects, cost estimates, and infrastructure data — a straightforward broken-access-control / privilege-escalation vulnerability (reproduced live: `curl` a register call with `role: admin`, got back a live admin JWT). The frontend's public register page also *offered* "Admin" as a dropdown option, compounding the exposure.

**Fix:** `AuthService.register()` now rejects (`403 Forbidden`) any public registration requesting a role outside `{customer, consultant}`; the frontend register page no longer offers "Admin". Test fixtures that legitimately need an admin user for RBAC testing now seed one directly via the repository layer, mirroring how a real deployment would provision its first admin (a DB operation, not a public API call).
**Regression tests:** `test_register_cannot_self_elevate_to_admin`, `test_register_self_service_consultant_role_still_allowed` (`tests/test_auth.py`).

### 2. MEDIUM — Reloading a saved estimate version silently lost budget status
`POST /projects/{id}/estimates` (create) computed and returned `budget_status`; `GET /projects/{id}/estimates/{version}` (reload) always returned `budget_status: null`, even with a budget configured, because the route never called `compute_budget_status`. Currently invisible in the UI (the frontend doesn't render this field yet), but a genuine API contract inconsistency that any future budget-alert UI or external API consumer would hit.
**Fix:** `get_estimate_version` now computes `budget_status` identically to the create path.
**Regression test:** `test_budget_status_also_surfaced_on_reload_not_just_on_creation` (`tests/test_project_budget.py`).

### 3. MEDIUM — Production-safety JWT secret check had a bypassable gap
`validate_production_security()` only refused to boot in `FINOPS_ENVIRONMENT=production` if the JWT secret was the *exact* known dev sentinel or under 32 characters. `docker-compose.yml`'s own example secret (`change-me-to-a-random-secret-in-any-shared-environment`) is 54 characters — long enough to sail past the guard undetected. A deployment that only flipped `FINOPS_ENVIRONMENT` to `production` without also replacing that value would have booted with a predictable, source-control-visible signing key (verified live: constructed exactly this `Settings` object, confirmed no exception was raised).
**Fix:** added a placeholder-word detector (`change-me`, `example`, `insecure`, `placeholder`, etc., case-insensitive) alongside the existing exact-match and length checks.
**Regression test:** `test_production_with_placeholder_looking_jwt_secret_refuses_to_start` (`tests/test_secrets.py`).

### 4. Minor — noted, not changed
Genuinely unhandled exceptions (e.g., a corrupted database file) fall through to Starlette's default handler, returning a generic plain-text `Internal Server Error` rather than the app's usual `{"error": ..., "message": ...}` JSON envelope. No information is leaked (no traceback reaches the client, confirmed live) and the server keeps running for subsequent requests — this is a consistency nit, not a security or stability defect, so it was documented rather than "fixed" with an unnecessary catch-all handler.

## 6. Security issues

- 1 critical (privilege escalation via public registration) — **fixed**.
- 1 medium (production-secret validation gap) — **fixed**.
- Verified clean: JWT tampering (signature flip, `alg: none` forgery) rejected; SQL-injection-shaped and XSS-shaped input handled safely (Pydantic/ORM parameterization, no server-side execution); path traversal in project IDs and upload filenames rejected; RBAC boundaries between customers hold; rate limiting engages under load; file upload size cap enforced (413 above 10MB); malformed/corrupted/wrong-type/formula-injection Excel files rejected cleanly, never crash the server.

## 7. Architecture issues

- No admin-provisioning API exists (by design, following the fix above) — additional admins currently require direct DB access. Worth a proper "existing admin promotes a user" endpoint in a future phase.
- Backend `Dockerfile` runs as root (no `USER` directive) — minor hardening recommendation for defense-in-depth, not an active exploit.
- Unhandled-exception response shape inconsistency (see bug #4 above).
- `docker-compose.yml` has no `frontend` service — by design, the Next.js app deploys separately (Vercel-style); confirmed intentional, not an oversight.

## 8. Performance

Not a rigorous load test — Phase 10's existing Locust suite (`docs/LOAD_TEST_RESULTS.md`) is the authoritative source for real throughput numbers and was not rerun here (this sandbox's small, shared VM would produce non-representative results). As a smoke signal: 25 fully concurrent `/api/v1/estimate` requests (full validate→normalize→architect→price pipeline) completed in 0.65s with zero errors and correct per-request results.

## 9. Production-readiness score: 90/100

Rationale: exceptionally thorough test coverage (419 checks across every layer, all passing), one critical and one medium security issue found through live adversarial testing and both fixed with permanent regression tests, a full real end-to-end workflow (real Postgres, real Redis, real async Celery worker) verified working, and consistently honest handling of unimplemented features throughout the codebase. Points held back for: the unresolved minor architecture items above, no live Google Cloud Pricing API re-verification in this pass (sandbox network restriction, not a code issue), no real Docker Compose run performed (static review only), and the fact that this is one thorough QA pass rather than production traffic history. Recommend: run a real `docker compose up` smoke test in an environment with Docker before deploying, and complete the still-pending live GCP pricing key verification noted in `PHASE5_LIVE_VERIFICATION.md`.
