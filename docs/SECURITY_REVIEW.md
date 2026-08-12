# Phase 10 Security Review

Conducted 2026-08-07 against the codebase as it stood at the end of Phase 9.
Methodology: automated dependency scanning (`pip-audit`, `npm audit`),
static analysis (`bandit`), and a manual review of input validation, auth,
rate limiting, audit-trail completeness, and secrets handling against the
actual source (not just the design docs). Every fix below was verified by
re-running the affected check and the full test suite (256 tests, all
passing) after the change - nothing here is a recommendation-only change
dressed up as done.

## Fixed this phase

### 1. Five backend dependencies with known CVEs
`pip-audit -r requirements.txt -r requirements-dev.txt` found 33 known
vulnerabilities across `starlette` (via `fastapi`), `pyjwt`, `pypdf`,
`python-multipart`, and `pytest`. Upgraded all five to patched versions
(`fastapi` 0.115.6 -> 0.141.1, which pulls a patched `starlette`; `pyjwt`
2.10.1 -> 2.13.0; `pypdf` 6.13.1 -> 6.14.2; `python-multipart` 0.0.20 ->
0.0.31; `pytest` 8.3.4 -> 9.0.3). Re-ran `pip-audit`: **0 vulnerabilities
remaining**. All 250 tests passing at the time (pre-Phase-10-additions)
required zero code changes - a clean upgrade, not a patch-and-pray.

### 2. Unauthenticated file-upload memory-exhaustion DoS
`POST /api/v1/intake/excel` has no authentication requirement at all (by
design - it's a stateless, try-before-you-commit endpoint), and it - along
with the authenticated per-project shortcut - called `await file.read()`
with no size limit. Any caller could upload an arbitrarily large file and
have the whole thing buffered into worker memory before the Excel parser
got a chance to reject it. Fixed with a bounded chunked reader
(`app/core/uploads.py::read_upload_bounded`, 1 MB chunks, aborts as soon as
`FINOPS_MAX_UPLOAD_SIZE_BYTES` - default 10 MB - is exceeded) wired into
both endpoints; oversized uploads now get a clean `413 payload_too_large`
instead of consuming unbounded memory. Tested with a monkeypatched 1 KB
limit so the test suite doesn't need a real 10 MB+ upload
(`tests/test_upload_limits.py`).

### 3. Production startup guard didn't check JWT secret strength, only its exact default value
`validate_production_security` (Phase 7) refused to boot with the *literal*
known-insecure default JWT secret, but a deployment that set
`FINOPS_JWT_SECRET_KEY=x` (or any short value) would sail through
undetected - technically "not the default," but far too short to be a real
HMAC-SHA256 key (PyJWT 2.13 itself now warns below 32 bytes, per RFC 7518
ยง3.2). Added a minimum-length check (32 chars) alongside the existing
exact-match check.

### 4. Production startup guard didn't check bcrypt work factor
`FINOPS_BCRYPT_ROUNDS` exists purely so the test suite can hash passwords
fast (`rounds=4`, see `tests/conftest.py`) - nothing previously stopped a
real deployment from copying that value from test docs/env files and
meaningfully weakening password hashing. Added a minimum-rounds check
(10) to the same production startup guard.

### 5. `/api/v1/auth/login` was only covered by the standard rate limit
The "heavy" (stricter) rate-limit bucket existed for CPU-expensive
endpoints (estimate/report/job/intake generation) but didn't include
login - meaning brute-force/credential-stuffing attempts against
`/api/v1/auth/login` were only throttled at the standard limit (120/min
default), far too permissive for a login endpoint specifically. Added it
to the heavy path-prefix list (20/min default) - a different rationale
than the other heavy endpoints (throttling attack attempts, not CPU cost),
documented as such in `app/core/config.py`.

## Reviewed, no issue found

- **SQL injection**: confirmed ORM-only query construction throughout
  (`grep` for raw-SQL string interpolation patterns found nothing; `bandit`
  independently confirms no `B608`-class findings). SQLAlchemy 2.0's
  `select()`/ORM query builder is used exclusively.
- **`bandit` static analysis**: one Low-severity finding
  (`B105 hardcoded_password_string` on
  `_KNOWN_INSECURE_JWT_SECRET = "insecure-dev-secret-change-me"` in
  `app/core/secrets.py`) - a false positive: this constant is the sentinel
  value the production startup guard *detects and refuses to boot with*,
  not a credential used for real authentication anywhere. Annotated with
  `# nosec B105` and an explanation so future CI runs of `bandit` don't
  re-flag it as new.
- **Frontend dependencies**: `npm audit --omit=dev` against all 708
  resolved packages: **0 vulnerabilities**.
- **Password policy**: minimum 8 characters enforced at registration
  (`app/domain/auth.py`), hashed with bcrypt (configurable work factor,
  now guarded at production-minimum 10 rounds per finding #4 above).
  Length-over-complexity is the NIST 800-63B-recommended approach - no
  further rule (special character requirements, etc.) was added.
- **RBAC**: three roles (`admin`/`consultant`/`customer`) enforced
  consistently through `ProjectService._authorize` and the
  `require_roles`/`get_current_user` dependency chain - exercised across
  every phase's test suite (project ownership isolation, admin bypass,
  403 on cross-user access).
- **Audit trail completeness**: every assumption, validation finding, and
  pricing decision is recorded via `AuditLogger` and persisted as
  queryable `AuditLogRowModel` rows (Phase 3), not just embedded in the
  JSON blob - verified this remains true through Phase 8's rightsizing/
  commitment/forecast engines (they reuse `EstimationService.generate_estimate`,
  so they inherit the same audit trail automatically rather than needing
  their own).
- **CORS**: defaults to allow-all (`*`) in local development only: the
  Phase 7 production startup guard already refused to boot with
  `FINOPS_ENVIRONMENT=production` and allow-all CORS.
- **CSRF**: not applicable - this is a pure JSON API authenticated via
  `Authorization: Bearer <JWT>`, never cookies, so there's no ambient
  credential for a CSRF attack to ride on.

## Known limitations (accepted, not fixed this phase - scope decisions)

- **Self-assignable `admin` role at registration**: flagged since Phase 3
  as an accepted limitation for this demo/internal-tool phase. Still true.
  A real deployment should restrict `admin` creation to an existing admin
  or a seed script - tracked here again as a concrete Phase-10-and-beyond
  recommendation, not silently dropped.
- **JWT tokens aren't revocable**: standard limitation of stateless JWT
  auth (no server-side session to invalidate). Default expiry is 24h
  (`FINOPS_JWT_EXPIRE_MINUTES`). A production deployment handling
  sensitive data should shorten this and add refresh-token rotation with a
  revocation list - out of scope for this phase (would meaningfully change
  the auth architecture, not a quick hardening pass).
- **No app-level security response headers**
  (`Strict-Transport-Security`, `X-Content-Type-Options`,
  `X-Frame-Options`, etc.): recommended to be set at the ingress/reverse-proxy
  layer instead of in FastAPI middleware - see `k8s/ingress.yaml`'s
  annotations in `docs/DEPLOYMENT.md`, which is the conventional place to
  set these in a Kubernetes deployment (they apply uniformly regardless of
  which backend service handles the request).

## Verification

```
pip-audit -r requirements.txt -r requirements-dev.txt   # 0 vulnerabilities
bandit -r app -q                                         # 1 Low finding, reviewed false positive (nosec'd)
npm audit --omit=dev                                      # 0 vulnerabilities (frontend)
pytest -q                                                  # 256 passed
```
