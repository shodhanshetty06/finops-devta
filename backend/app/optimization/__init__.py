"""
Phase 8 FinOps optimization engines: rightsizing, committed-use discount
recommendations, cost forecasting, carbon footprint estimation, and
region/scenario comparison.

Same invariant as every other phase: nothing here invents a dollar figure.
Every engine that needs a price re-runs the existing `EstimationService`
pipeline (validation -> normalization -> pricing via `PricingProvider`)
rather than approximating a cost itself. The only genuinely new numeric
approximations introduced in this phase are non-pricing estimates that this
platform has no authoritative source for (utilization-based sizing targets,
carbon intensity), and those are documented as illustrative assumptions in
each engine's module docstring and in `docs/ROADMAP.md`.
"""
