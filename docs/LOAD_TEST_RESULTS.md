# Phase 10 load test results

Load test tool: [Locust](https://locust.io) 2.46.0, scenario in
`backend/loadtest/locustfile.py`. Run against a real `uvicorn` process (same
launch pattern as `tests_integration/`), not the in-process `TestClient`.

## Environment (important caveats)

This was run inside the sandboxed dev environment used to build this
platform, **not** production infrastructure:

- 2 vCPUs, ~3 GB RAM, shared with the rest of the sandbox.
- A single `uvicorn` process, one worker, no `gunicorn`/process manager.
- SQLite backing the database (`FINOPS_DATABASE_URL=sqlite:///...`), not the
  Postgres the platform actually deploys with (`docker-compose.yml`).
- `FINOPS_BCRYPT_ROUNDS=4` (the same reduced-cost setting the test suites
  use) rather than the production-minimum of 10 enforced by
  `validate_production_security()` - real login/register latency in
  production will be higher because bcrypt is deliberately slow.
- `FINOPS_RATE_LIMIT_ENABLED=false`, so these numbers do not reflect the
  rate limiter's throttling behavior (that's covered separately by
  `backend/tests/test_rate_limit.py`, not by this load test).

These numbers are therefore a **relative baseline** for catching regressions
in this codebase (e.g. "did the Phase 11 change make `/estimate` 5x slower"),
not an absolute production capacity figure. A production capacity test
should be re-run against a real Postgres instance, `FINOPS_BCRYPT_ROUNDS=12`,
and the actual container resource limits before being used for capacity
planning.

## Scenario

Two simulated user types running concurrently, ramped to 30 concurrent users
over 5 seconds, sustained for 45 seconds:

- **`AnonymousEstimateUser`** (weight 3, the dominant traffic pattern):
  repeatedly calls `POST /api/v1/estimate` with a jittered requirement
  (varying vCPU/instance count so nothing is trivially cached) - the
  unauthenticated validate -> normalize -> price -> assumption-log pipeline
  that every questionnaire submission runs.
- **`RegisteredUserJourney`** (weight 1): registers once, logs in, creates a
  project, then repeatedly creates estimate versions
  (`POST /api/v1/projects/{id}/estimates`, a DB write) and calls
  `POST /api/v1/optimization/compare-clouds` (the most CPU-expensive single
  endpoint - it runs the full pricing pipeline three times, once per cloud).

All `/api/v1/optimization/*` endpoints require authentication
(`Depends(get_current_user)` on every route in
`app/api/routers/optimization.py`), so `compare-clouds` runs under the
registered-user class with a bearer token, not anonymously.

## Results

929 requests total in the first run surfaced a **test-script bug**, not an
app bug: `compare-clouds` was initially called anonymously and got a
(correct) `401 Unauthorized` on every call. Fixed by moving that task under
`RegisteredUserJourney` with its auth header. Second run, clean:

| Endpoint | Requests | Failures | Median | p95 | p99 | Max |
|---|---|---|---|---|---|---|
| `POST /api/v1/estimate` | 730 | 0 | 18ms | 63ms | 160ms | 201ms |
| `POST /api/v1/optimization/compare-clouds` | 41 | 0 | 35ms | 74ms | 150ms | 152ms |
| `POST /api/v1/projects/{id}/estimates` (create version) | 119 | 0 | 110ms | 190ms | 240ms | 249ms |
| `POST /api/v1/projects` (create) | 8 | 0 | 75ms | 180ms | 180ms | 179ms |
| `POST /api/v1/auth/register` | 8 | 0 | 110ms | 180ms | 180ms | 183ms |
| `POST /api/v1/auth/login` | 8 | 0 | 31ms | 62ms | 62ms | 62ms |
| **Aggregated** | **914** | **0** | **23ms** | **130ms** | **180ms** | **249ms** |

Overall throughput: ~20.7 requests/second sustained, **zero failures**, on
2 shared vCPUs with no process-level parallelism.

## Findings

1. **The core pricing pipeline is fast and dominates capacity in a good
   way.** `/api/v1/estimate` - the full validate/normalize/price pipeline -
   has an 18ms median and stays under 100ms at p90 even under concurrent
   load. It's also the highest-volume endpoint in the scenario (730 of 914
   requests), so the aggregate p95/p99 numbers are mostly this endpoint's
   distribution, not a slower one dragging the average up.
2. **`compare-clouds` is proportionally slower, as expected** (median
   35ms vs. 18ms for a single-cloud estimate) since it runs the pricing
   pipeline three times per request. It's still well within an interactive
   response budget even single-worker on 2 vCPUs.
3. **DB-write endpoints (register, create project, create estimate version)
   are the slowest class**, 75-110ms median. `register`'s cost is expected
   and intentional (bcrypt password hashing - even at the reduced
   `BCRYPT_ROUNDS=4` used here); `create estimate version`'s ~110ms is the
   pricing pipeline plus a SQLite write plus audit-log persistence. Neither
   is a bottleneck at this concurrency, but they're the endpoints to
   re-benchmark first if a future load test target is raised well beyond
   30 concurrent users.
4. **Zero failures at 30 concurrent users** on a 2-vCPU box with a single
   worker process and SQLite is a reasonable baseline signal that there's no
   gross resource leak or connection-pool exhaustion bug under load - but it
   is not, by itself, evidence of production capacity at any specific
   target QPS. See the environment caveats above.

## How to re-run

```bash
cd backend
pip install locust
# start a live server the same way tests_integration/conftest.py does, e.g.:
FINOPS_DATABASE_URL="sqlite:////tmp/loadtest.db" FINOPS_AUTO_CREATE_TABLES=true \
  FINOPS_ENVIRONMENT=development FINOPS_JWT_SECRET_KEY="<32+ chars>" \
  FINOPS_CELERY_TASK_ALWAYS_EAGER=true FINOPS_CELERY_RESULT_BACKEND="cache+memory://" \
  uvicorn app.main:app --host 127.0.0.1 --port 8811 &

locust -f loadtest/locustfile.py --host http://127.0.0.1:8811 \
  --headless -u 30 -r 5 -t 45s --csv loadtest/results/run
```
