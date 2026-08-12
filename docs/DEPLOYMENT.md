# Kubernetes deployment guide

Manifests live in `k8s/`. This mirrors what `docker-compose.yml` runs for
local dev (backend, celery-worker, postgres, redis) plus the pieces that
only make sense in a real cluster: a migration Job, an HPA, a
PodDisruptionBudget, and an Ingress.

**Sandbox note**: this guide and the manifests were written and syntax-
validated (`python -c "import yaml; yaml.safe_load_all(...)"` against every
file) in the same sandboxed environment used to build the rest of this
platform, which has no `kubectl`, `kustomize`, or `docker` binary available
(consistent with the constraint already noted for Docker image builds in
`docs/SECURITY_REVIEW.md` / the CI `docker-build` job). The manifests could
not be applied to a real cluster or dry-run validated with `kubectl apply
--dry-run=client` from here. Run the "Verify" steps near the end of this
guide against a real cluster before trusting this for a first production
deploy.

## Prerequisites

- A Kubernetes cluster (1.27+) with a default `StorageClass` (for Postgres's
  `PersistentVolumeClaim`) and, if you want the `ingress.yaml` as-is, an
  `ingress-nginx` controller and `cert-manager` already installed.
- `kubectl` configured against that cluster.
- A container registry you can push to (Docker Hub, GCR/Artifact Registry,
  ECR, etc.).
- Docker (or any OCI-compatible builder) to build `backend/Dockerfile`.

## 1. Build and push the backend image

```bash
cd backend
docker build -t <your-registry>/gcp-finops-backend:<tag> .
docker push <your-registry>/gcp-finops-backend:<tag>
```

Then update the `image:` line in `k8s/backend.yaml`,
`k8s/celery-worker.yaml`, and `k8s/migration-job.yaml` (all three currently
say `gcp-finops-backend:latest` as a placeholder) to
`<your-registry>/gcp-finops-backend:<tag>`.

There is no frontend manifest here yet - the frontend (`frontend/`) is a
static Next.js app better suited to a CDN/static host (Vercel, Cloud Run,
a `next export` + object storage bucket) than a stateful cluster workload.
If you do want it in-cluster, it needs its own `Dockerfile` (not present in
this repo yet) and Deployment/Service, following the same pattern as
`backend.yaml`.

## 2. Create the real Secret

`k8s/secret.yaml.example` is a template with placeholder base64 values -
copy it and fill in real ones. **Never commit the filled-in file** (already
covered by `.gitignore`: `k8s/secret.yaml`).

The safest way to fill it in is to build the Secret imperatively so real
credentials never touch a file on disk at all:

```bash
kubectl create namespace finops --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic finops-secrets -n finops \
  --from-literal=FINOPS_JWT_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" \
  --from-literal=POSTGRES_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')" \
  --from-literal=FINOPS_DATABASE_URL="postgresql+psycopg2://finops:<same-password-as-above>@finops-postgres:5432/finops"
  # Optional, only if FINOPS_PRICING_PROVIDER=gcp in configmap.yaml:
  # --from-file=FINOPS_GCP_SERVICE_ACCOUNT_JSON=/path/to/service-account.json
```

`FINOPS_JWT_SECRET_KEY` must be a real random 32+ character value -
`validate_production_security()` (`backend/app/core/secrets.py`) refuses to
boot with `FINOPS_ENVIRONMENT=production` (set in `configmap.yaml`) and
anything shorter, or the literal dev default. The same function also
refuses to boot if `FINOPS_BCRYPT_ROUNDS` is below 10 or
`FINOPS_CORS_ALLOW_ORIGINS` is still `["*"]` - both are already set safely
in `configmap.yaml`, but if you override either, keep them within those
bounds or the backend Pods will crash-loop on startup with a clear error
message (not silently misconfigured).

## 3. Review configmap.yaml

Edit `k8s/configmap.yaml` before applying:

- `FINOPS_CORS_ALLOW_ORIGINS` - set to your real frontend origin(s).
- `FINOPS_PRICING_PROVIDER` - `mock` by default (zero external
  dependencies); set to `gcp` once you've added the GCP service account
  Secret key above.
- `FINOPS_CLOUD_PROVIDER` - `gcp` | `aws` | `azure` (Phase 9); AWS/Azure are
  mock-catalog-only right now, see `docs/ROADMAP.md`.

## 4. Apply the base stack (everything except the migration Job)

```bash
kubectl apply -k k8s/
# or individually, in this order, if you're not using kustomize:
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml       # the real one you created/filled in above
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
```

Wait for Postgres to be ready before proceeding (the migration Job doesn't
retry connection failures beyond `backoffLimit: 2`):

```bash
kubectl rollout status statefulset/finops-postgres -n finops
```

## 5. Run the migration Job

Schema changes go through Alembic explicitly (`FINOPS_AUTO_CREATE_TABLES`
is `false` in `configmap.yaml`) rather than the auto-create-on-boot
convenience used in local dev - run this once per deploy, before rolling
out the backend/celery-worker, whenever `backend/alembic/versions/` has new
migrations:

```bash
kubectl apply -f k8s/migration-job.yaml
kubectl wait --for=condition=complete --timeout=120s job/finops-migrate -n finops
kubectl logs job/finops-migrate -n finops   # confirm it printed the expected "Running upgrade ..." lines
kubectl delete job/finops-migrate -n finops  # Jobs don't self-clean; delete before re-applying on the next deploy
```

## 6. Roll out the application

```bash
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/celery-worker.yaml
kubectl apply -f k8s/ingress.yaml   # after updating the host to your real domain
```

## 7. Verify

```bash
kubectl get pods -n finops
kubectl rollout status deployment/finops-backend -n finops
kubectl rollout status deployment/finops-celery-worker -n finops

# Smoke-test the API from inside the cluster (before DNS/ingress is live):
kubectl run -n finops curl-test --rm -it --image=curlimages/curl --restart=Never -- \
  curl -s http://finops-backend/health

# Once the Ingress/DNS is live:
curl -s https://api.your-finops-domain.example/health
```

A healthy response looks like what `docker-compose.yml`'s healthcheck
expects: `{"status": "ok", ...}`. If `/health` never comes up, check
`kubectl logs deployment/finops-backend -n finops` first - the most likely
cause is `validate_production_security()` refusing to boot (see step 2), or
the migration Job not having completed (step 5).

For a fuller functional check, adapt
`backend/tests_integration/test_full_user_journey.py` to point at the real
`api.your-finops-domain.example` host instead of spawning a local `uvicorn`
subprocess - it already exercises register/login/intake/estimate/every
optimization endpoint/export/async-job/RBAC in one continuous run.

## Updating a running deployment

```bash
docker build -t <your-registry>/gcp-finops-backend:<new-tag> backend/
docker push <your-registry>/gcp-finops-backend:<new-tag>
# update the image: line in backend.yaml, celery-worker.yaml, migration-job.yaml
kubectl apply -f k8s/migration-job.yaml && kubectl wait --for=condition=complete --timeout=120s job/finops-migrate -n finops && kubectl delete job/finops-migrate -n finops
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/celery-worker.yaml
kubectl rollout status deployment/finops-backend -n finops
```

`backend.yaml`'s Deployment uses the default `RollingUpdate` strategy, so
this is a zero-downtime rollout as long as the migration is backward-
compatible with the previous version's code (the usual expand/contract
migration discipline - not something these manifests enforce for you).

## What's deliberately out of scope here

- **Frontend deployment** - no Dockerfile or manifest yet; see the note in
  step 1.
- **Managed Postgres/Redis** - `postgres.yaml`/`redis.yaml` self-host both
  for a complete, dependency-free manifest set. Swapping in Cloud SQL /
  Memorystore / RDS / ElastiCache for real production traffic just means
  pointing `FINOPS_DATABASE_URL`/`FINOPS_REDIS_URL` at the managed
  endpoint and deleting `postgres.yaml`/`redis.yaml`.
- **Network policies / service mesh** - not included; add
  `NetworkPolicy` resources appropriate to your cluster's baseline security
  posture.
- **Observability stack** (Prometheus/Grafana/log aggregation) -
  `FINOPS_REQUEST_LOGGING_ENABLED=true` (set in `configmap.yaml`) makes the
  backend emit structured request logs to stdout, which any cluster log
  collector (Fluent Bit, Cloud Logging, etc.) picks up automatically; no
  extra sidecar is defined here.
- **Capacity planning** - the resource `requests`/`limits` in
  `backend.yaml`/`celery-worker.yaml`/`postgres.yaml`/`redis.yaml` are
  starting points, not measured production figures - see
  `docs/LOAD_TEST_RESULTS.md`'s environment caveats before treating them as
  sized for real traffic.
