# Phase 5 - Live Verification Checklist

**Update (2026-08-12): live verification complete.** Run from a machine
with real internet access (`python -m scripts.verify_gcp_pricing` against
`backend/secrets/gcp-service-account.json`), all 7 checks passed - a real
HTTP round trip through Google auth, the Cloud Billing Catalog API, SKU
matching, and pricing math. Two real SKU-matching bugs were found and fixed
in the process (see below); everything else matched on the first try.
Everything below this note describes the state *before* that run, kept for
context.

Everything in Phase 5 (`app/pricing/gcp_client.py`, `sku_matcher.py`,
`cache.py`, `gcp_provider.py`) is built against the Cloud Billing Catalog
API's documented response schema and tested against realistic hand-built
fixtures (`tests/test_gcp_client.py`, `test_sku_matcher.py`,
`test_sku_cache.py`, `test_gcp_pricing_provider.py`) - 57 tests, all
passing. What has **not** been done is a real HTTP round-trip to Google,
because the sandbox this was built in has no network path to Google's
domains. This is the one remaining step before treating live pricing as
verified end-to-end.

## Bugs found and fixed by the live run (2026-08-12)

Two of the seven checks failed on the first live run - both were exactly
the "SKU description drifted from the assumed keyword" scenario this
document called out as the one realistic risk, not a structural problem:

1. **Network egress** (`find_network_egress_sku`): the matcher looked for
   `"internet egress"` in the description; Google's real SKU text is
   `"Standard Data Transfer Out to Internet from <city>"` - the word
   "egress" never appears. Fixed by matching `"data transfer out to
   internet"` + `"standard"` (excluding `"vpn"`, a different SKU family).
2. **GKE cluster management fee** (`find_gke_management_sku`): the matcher
   looked for `"cluster management"` + `"standard"/"autopilot"`; Google's
   real SKU text is `"Zonal Kubernetes Clusters"` / `"Regional Kubernetes
   Clusters"` / `"Autopilot Kubernetes Clusters"` - no "cluster management"
   wording, and Standard mode has separate Zonal/Regional SKUs where this
   provider's interface (`get_gke_cluster_management_hourly_price(autopilot)`)
   only takes an autopilot flag. Fixed by matching the Zonal SKU for
   Standard mode (the cheaper, more common topology) - documented as a
   simplification in `sku_matcher.py`, same status as the flat CUD/SUD
   discount percentages already documented in `gcp_provider.py`.

Both fixes updated `app/pricing/sku_matcher.py` and the corresponding
fixtures in `tests/test_sku_matcher.py`/`test_gcp_pricing_provider.py` to
match the real description text - no change to the matching *strategy*
(keyword/category filtering + structured `serviceRegions`), only the
keywords themselves. The other five checks (N2/E2 compute core+RAM,
pd-ssd disk, T4 GPU, Cloud SQL db-f1-micro) matched correctly with no
changes.

One more thing observed, not a bug: network egress priced at exactly
`0.00` for the tested quantity - this is `sku_matcher.py`'s already-documented
"only the SKU's first pricing tier is modeled" simplification (see
`gcp_provider.py`'s module docstring) intersecting with a free egress tier,
not a mismatch.

## Why this matters

`sku_matcher.py`'s keyword patterns (e.g. `"N2 Instance Core running in
Americas"`, `"Storage PD Capacity"`) are based on Google's publicly
documented SKU description conventions, not fetched live. Google doesn't
version these strings, so there's a small chance the live catalog phrases
something slightly differently than assumed. A live run either confirms
the patterns hold, or pinpoints exactly which one needs a tweak - it should
not require any structural code changes either way.

## How to verify (run this outside the sandbox, anywhere with normal internet access)

1. Set the environment variables (already present in your `.env` if you
   copied `backend/.env.example`):
   ```
   FINOPS_PRICING_PROVIDER=gcp
   FINOPS_GCP_SERVICE_ACCOUNT_JSON=/path/to/your-service-account-key.json
   ```
2. From `backend/`, run:
   ```
   python -m scripts.verify_gcp_pricing
   ```
   This calls the real API for a handful of representative lookups
   (N2/E2 compute in us-central1, a pd-ssd disk, a T4 GPU, a Cloud SQL
   `db-f1-micro` instance, network egress) and prints the resolved price
   for each, or a clear error naming exactly which SKU pattern didn't
   match if one fails.
3. If everything prints a plausible USD price, live pricing is confirmed
   end-to-end and `FINOPS_PRICING_PROVIDER=gcp` is safe to leave enabled.
4. If a specific lookup fails, the error message includes the resource
   description that was searched for - compare it against the actual SKU
   list for that service (the script also has a `--dump-skus "Compute
   Engine"` mode to print every SKU description Google actually returned,
   to find the correct wording) and adjust the corresponding keyword in
   `app/pricing/sku_matcher.py`.

## Credential handling note

The service account key used during development was saved to
`backend/secrets/` for local testing convenience and is excluded from
version control via `.gitignore` (`backend/secrets/`). It does not need to
live there - pointing `FINOPS_GCP_SERVICE_ACCOUNT_JSON` at wherever you
keep the key file works identically.
