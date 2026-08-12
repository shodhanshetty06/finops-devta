# System Architecture

## Design principles

- **Pricing never comes from the AI.** Every dollar amount in a `CostBreakdown`
  is produced by a `PricingProvider` implementation (`app/pricing/base.py`).
  The AI/business-logic layers (validation, normalization, recommendation,
  architecture) only decide *what* to price, never *how much* it costs.
- **Clean layering, dependency inversion.** Business logic depends on
  abstractions (`CatalogProvider`, `PricingProvider`), never on concrete data
  sources. Concrete mock implementations live in `mock_provider.py` files;
  live Google Cloud implementations will live in `gcp_provider.py` files with
  the exact same interface, wired in via `app/*/dependency.py` factories.
- **No hidden assumptions.** Any time the platform substitutes a requested
  value for a supported one, it is recorded as an `Assumption`
  (`app/domain/assumption.py`) and surfaced through the API response, audit
  log, and (in later phases) Excel/PDF exports.
- **Every validation finding is structured.** `ValidationResult` always
  carries requested value, supported value, reason, severity, and
  recommendation - never a bare pass/fail boolean.

## Request pipeline (`EstimationService.generate_estimate`)

```
CustomerRequirement (untrusted input)
        |
        v
[1] AI Recommendation Engine   -- only runs if `compute` is missing
        |                          (business-context-only submissions)
        v
[2] Validation Rule Engine     -- 13 rules, each catalog-aware
        |
        v
[3] Blocker check              -- raises ValidationFailedError unless force=True
        |
        v
[4] Normalization Engine       -- strategy-driven substitution to valid specs
        |
        v
[5] Architecture Engine        -- descriptive recommended architecture
        |
        v
[6] Pricing Engine             -- delegates all $ amounts to PricingProvider
        |
        v
[7] Audit Logger               -- records every step above
        |
        v
EstimateResult (API response)
```

## Module map (backend/app)

| Module | Responsibility |
|---|---|
| `core/` | Settings (env-driven), exceptions, logging |
| `domain/` | Pydantic schemas shared across all layers (the only "vocabulary" every module speaks) |
| `catalog/` | What configurations *exist* (machine types, disks, regions, GPUs, Cloud SQL tiers, GKE limits) |
| `validation/` | Rule engine: is a requested config valid against the catalog? |
| `normalization/` | Strategy engine: resolve invalid values to valid ones (conservative/balanced/performance) |
| `pricing/` | What configurations *cost* - the only place dollar amounts are computed |
| `services/` | Orchestration: `EstimationService`, `ArchitectureEngine`, `RecommendationEngine` |
| `audit/` | Structured, ordered decision log for every estimate |
| `api/` | FastAPI routers + dependency injection wiring |

## Live Google Cloud pricing source (Phase 5, implemented)

`app/pricing/gcp_provider.py::GcpPricingProvider(PricingProvider)`, backed by
`https://cloudbilling.googleapis.com` (Cloud Billing Catalog API), is wired
into `app/pricing/dependency.py::get_pricing_provider()` - set
`FINOPS_PRICING_PROVIDER=gcp` plus `FINOPS_GCP_SERVICE_ACCOUNT_JSON` (or
`FINOPS_GCP_API_KEY`) to activate it; no code changes needed to cut over.
`ValidationRuleEngine`, `NormalizationEngine`, and `EstimationService` needed
zero changes - they only depend on the `PricingProvider` interface.

### Known limitation: the validation catalog stays mock even when pricing is live

**No `GcpCatalogProvider` has been built** - `app/catalog/dependency.py`
always returns `MockCatalogProvider` for `FINOPS_CLOUD_PROVIDER=gcp`,
regardless of `FINOPS_PRICING_PROVIDER`. This means validation ("is this
region/machine family/disk type supported?") always runs against the mock
catalog's supported-value sets, which mirror Google's real catalog closely
but are not fetched live. In principle this could let a configuration pass
validation as "supported" and then fail at the live pricing step because no
matching SKU was found.

In practice this can never happen *silently*: `GcpPricingProvider`/
`sku_matcher.py` raise `PricingProviderError` (mapped to HTTP 502 in
`app/main.py`) with a message naming exactly which SKU pattern didn't match
rather than returning an incomplete or zero-cost line item - so a
validation/pricing mismatch always surfaces as a loud, actionable error, not
a quietly-wrong total. Building a full live `GcpCatalogProvider` (fetching
supported regions/machine types/disk types from the real Compute Engine /
Cloud SQL Admin / GKE APIs) remains a legitimate follow-up - tracked here as
a known gap, not silently left inconsistent - but is a materially larger
scope item than the pricing integration was, since it would need to mirror
several different GCP admin APIs rather than one billing catalog endpoint.

To extend catalog resolution to a live source:
1. Implement `app/catalog/gcp_provider.py::GcpCatalogProvider(CatalogProvider)`.
2. Wire it into `app/catalog/dependency.py::get_catalog_provider()`'s
   `cloud_provider == "gcp"` branch (currently hardcoded to `MockCatalogProvider()`).

No other module changes required - the same interface-only dependency
`ValidationRuleEngine`/`NormalizationEngine` already have on `CatalogProvider`
applies here too.

## Extending to AWS / Azure

The `CatalogProvider` / `PricingProvider` interfaces are cloud-agnostic by
design (machine types, disk types, regions, GPU types are generic concepts).
A future `AwsCatalogProvider` / `AwsPricingProvider` pair implementing the
same interfaces, selected via a `FINOPS_CLOUD_PROVIDER=aws` setting, is the
intended extension point. The `domain/` schemas would gain a `cloud_provider`
field so a single `EstimateResult` can in principle mix or compare providers
in a future multi-cloud comparison feature (see ROADMAP.md).

## Current scope

See `docs/ROADMAP.md` for the full phase-by-phase breakdown (frontend,
auth/RBAC, persistence, async jobs, Excel/PDF, live GCP pricing, FinOps
optimization, multi-cloud, production hardening are all complete as of
Phase 10). The one explicitly deferred item is the live `GcpCatalogProvider`
described above.
