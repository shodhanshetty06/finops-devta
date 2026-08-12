# Integration tests

Distinct from `backend/tests/` (256 unit/API-level tests run in-process
against Starlette's `TestClient` and a throwaway SQLite file per test - fast,
fully isolated, run on every `pytest -q`). This directory holds **full
user-journey tests** that:

- launch a real `uvicorn` server in a subprocess and talk to it over real
  HTTP (`httpx`, not the in-process ASGI transport `TestClient` uses), and
- walk one continuous session through most of the platform in a single test
  (register -> create project -> Excel intake -> estimate -> every Phase 8
  optimization endpoint -> Phase 9 cross-cloud comparison -> budget -> a
  second estimate version -> version comparison -> Excel/PDF export -> an
  async report job polled to completion), proving the pieces work together
  as a real client would exercise them, not just each endpoint in isolation.

Deliberately **not** under `backend/tests/` and **not** picked up by a plain
`pytest -q` (which respects `pytest.ini`'s `testpaths = tests`) - these are
slower (real subprocess + real HTTP + real Celery-eager execution) and
shouldn't be part of the fast inner-loop suite. Run them explicitly:

```bash
cd backend
pytest tests_integration -v
```

## Database coverage

By default this runs against a throwaway SQLite file, same as the main
suite. To additionally run the exact same journey against a real Postgres
(what `docker-compose.yml` actually deploys), set
`FINOPS_TEST_POSTGRES_URL` before running:

```bash
docker compose up -d postgres   # from the repo root
FINOPS_TEST_POSTGRES_URL="postgresql+psycopg2://finops:finops_dev_password@localhost:5432/finops" \
  pytest tests_integration -v
```

Without that variable set, the Postgres-specific test is **skipped**, not
silently passed - `pytest -v` will show it as `SKIPPED` with the reason, so
its absence is never mistaken for a green result. This sandbox has no
Docker/Postgres access, so that variable was never set here; the
`.github/workflows/ci.yml` `integration-tests` job runs it for real against
a GitHub Actions Postgres service container on every push.
