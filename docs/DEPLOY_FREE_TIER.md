# Free-tier deployment guide (Vercel + Render + Neon)

This is the "get it live for $0" path, as opposed to `docs/DEPLOYMENT.md`
(the Kubernetes guide for a real production cluster). It deploys 3 of the
5 `docker-compose.yml` services and skips two on purpose:

| Service (docker-compose) | Where it goes here | Included? |
|---|---|---|
| `frontend/` (Next.js) | **Vercel** | Yes |
| `backend` (FastAPI, `backend/Dockerfile`) | **Render** (free Web Service) | Yes |
| `postgres` | **Neon** (free serverless Postgres) | Yes |
| `redis` | none | Skipped - everything that uses Redis has an automatic in-memory fallback (`app/pricing/cache.py`, `app/middleware/rate_limit.py`) |
| `celery-worker` / `celery-beat` | none | Skipped - Render's free plan doesn't support Background Worker services (needs a paid instance). `/api/v1/jobs/*` will still accept requests but jobs stay `PENDING` forever; the daily audit-log purge won't run. Nothing else in the app depends on this. |

Add Redis + a paid Celery worker later (see "Upgrading later" at the
bottom) once you actually need async report generation.

Why Neon instead of Render's own free Postgres: Render's free Postgres
databases are deleted after ~30 days of the free trial. Neon's free tier
has no expiry, which matters if this is meant to stay live.

## 0. Prerequisites

- The repo is already on GitHub: `shodhanshetty06/finops-devta`, branch
  `main`, clean working tree - confirmed before writing this guide.
- Accounts (all free, sign up with GitHub for one-click repo import):
  [neon.tech](https://neon.tech), [render.com](https://render.com),
  [vercel.com](https://vercel.com).

## 1. Database - Neon

1. Neon dashboard -> **New Project** -> any name/region -> **Postgres 16**.
2. On the project page, copy the **connection string** shown (looks like
   `postgresql://<user>:<password>@<host>/<dbname>?sslmode=require`).
   Keep this tab open - you'll paste it in two places.
3. SQLAlchemy's default `postgresql://` dialect resolves to `psycopg2`
   (already in `backend/requirements.txt`), so you do **not** need to
   rewrite it to `postgresql+psycopg2://` - use the string as-is.

## 2. Apply the schema (Alembic) - run this from your own machine

Do this once, before the backend serves any traffic, and again after any
future migration is added to `backend/alembic/versions/`:

```bash
cd backend
pip install -r requirements.txt   # if you haven't already
# PowerShell:
$env:FINOPS_DATABASE_URL = "postgresql://<user>:<password>@<host>/<dbname>?sslmode=require"
alembic upgrade head
```

Confirm it printed `Running upgrade ... -> 0002_add_project_budget.py`
(the latest revision) with no errors.

## 3. Backend - Render

1. Render dashboard -> **New** -> **Web Service** -> **Build and deploy
   from a Git repository** -> connect GitHub -> select `finops-devta`.
2. Configure:
   - **Root Directory**: `backend`
   - **Runtime**: **Docker** (Render auto-detects `backend/Dockerfile`
     once Root Directory is set to `backend`)
   - **Instance Type**: **Free**
   - **Health Check Path**: `/health`
3. Environment variables (Render dashboard -> Environment):

   | Key | Value |
   |---|---|
   | `FINOPS_ENVIRONMENT` | `production` |
   | `FINOPS_DATABASE_URL` | the Neon connection string from step 1 |
   | `FINOPS_AUTO_CREATE_TABLES` | `false` |
   | `FINOPS_JWT_SECRET_KEY` | a random value - generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`, paste the output |
   | `FINOPS_PRICING_PROVIDER` | `gcp` for real Google Cloud list pricing (needs step 3b below); `mock` if you want to defer GCP credential setup and use deterministic mock catalog prices for now - the app boots either way and only logs a warning on `mock` in production |
   | `FINOPS_CLOUD_PROVIDER` | `gcp` |
   | `FINOPS_CORS_ALLOW_ORIGINS` | `["http://localhost:3000"]` for now - you'll change this in step 5 once the Vercel URL exists |

   Leave `FINOPS_REDIS_URL` unset - the app falls back to in-memory
   automatically.

3b. **(Only if `FINOPS_PRICING_PROVIDER=gcp`)** wire up a GCP credential -
   never put the raw service-account JSON in an env var:
   - Render dashboard -> your service -> **Environment** -> **Secret
     Files** -> add a file, path `/etc/secrets/gcp-service-account.json`,
     paste the service account key JSON as its content (the same file used
     locally at `backend/secrets/gcp-service-account.json`, which is
     gitignored and must never be committed).
   - Add env var `FINOPS_GCP_SERVICE_ACCOUNT_JSON` =
     `/etc/secrets/gcp-service-account.json`.
   - Simpler alternative: skip the secret file and set
     `FINOPS_GCP_API_KEY` to a Cloud Billing API key instead (only needs
     the "Cloud Billing API" scope, no project IAM roles).

   These three are enforced by `validate_production_security()`
   (`backend/app/core/secrets.py`) - the app **refuses to boot** with
   `FINOPS_ENVIRONMENT=production` if the JWT secret is short/default, CORS
   is `["*"]`, or auto-create-tables is left on. If the Render deploy logs
   show a crash-loop right after "Application startup", this is almost
   always why - check the exact error message it prints.

4. **Create Web Service**. First build takes a few minutes (installs
   `build-essential` + pip deps per the Dockerfile). Render gives you a URL
   like `https://finops-devta-backend.onrender.com` - copy it.
5. Verify: `curl https://finops-devta-backend.onrender.com/health` should
   return `{"status": "ok", ...}`. Also check `/docs` in a browser for the
   Swagger UI.

   Note: Render's free plan spins the service down after 15 minutes of no
   traffic. The next request wakes it up but takes 30-50s - expected on
   free tier, not a bug.

## 4. Frontend - Vercel

1. Vercel dashboard -> **Add New** -> **Project** -> import
   `finops-devta` from GitHub.
2. Configure:
   - **Root Directory**: `frontend` (click "Edit" next to Root Directory
     and select it - Vercel then auto-detects Next.js and fills in the
     build/output settings from `frontend/package.json`)
   - **Environment Variables**: add
     `NEXT_PUBLIC_API_BASE_URL` = `https://finops-devta-backend.onrender.com`
     (your real Render URL from step 3, no trailing slash)
3. **Deploy**. Vercel gives you a URL like
   `https://finops-devta.vercel.app`.

## 5. Wire CORS back to the real frontend URL

Back in Render -> your backend service -> Environment:

- Update `FINOPS_CORS_ALLOW_ORIGINS` to
  `["https://finops-devta.vercel.app"]` (your real Vercel URL; add more
  origins as a JSON array if you also keep `http://localhost:3000` for
  local dev, e.g. `["https://finops-devta.vercel.app","http://localhost:3000"]`).
- Save - Render auto-redeploys the service with the new value.

## 6. Verify the whole thing end to end

1. Open the Vercel URL in a browser.
2. Register a user, log in.
3. Run the questionnaire wizard through to a priced estimate.
4. Export it to Excel/PDF (this hits `/api/v1/projects/{id}/estimates/{v}/reports/{excel,pdf}`,
   which is synchronous - not one of the skipped Celery job endpoints - so
   it works without a worker).

If step 2/3 fails with a CORS error in the browser console, double-check
step 5 - the value must be valid JSON and must exactly match the Vercel
origin (scheme + host, no path, no trailing slash).

## Upgrading later

- **Add Redis**: Render -> New -> Key Value (Render's current name for
  managed Redis) -> free or paid plan -> copy its internal connection
  string into the backend's `FINOPS_REDIS_URL` env var. No code or
  redeploy-logic changes needed - `app/pricing/cache.py` and
  `app/middleware/rate_limit.py` pick it up automatically.
- **Add the Celery worker**: Render -> New -> Background Worker (paid,
  ~$7/mo on the cheapest instance) -> same repo, **Root Directory**
  `backend`, **Docker Command** override:
  `celery -A app.tasks.celery_app.celery_app worker --loglevel=INFO`.
  Same env vars as the backend web service, plus `FINOPS_REDIS_URL` now
  required (Celery has no in-memory fallback, unlike the cache/rate
  limiter). Add a second Background Worker with command
  `celery -A app.tasks.celery_app.celery_app beat --loglevel=INFO` for the
  scheduled audit-log purge - only ever run one `beat` instance.
- **Custom domain**: both Vercel and Render support adding your own domain
  under their respective project settings; update
  `NEXT_PUBLIC_API_BASE_URL` and `FINOPS_CORS_ALLOW_ORIGINS` to match once
  you do.
- **Full production / Kubernetes**: see `docs/DEPLOYMENT.md` once traffic
  outgrows this setup.
