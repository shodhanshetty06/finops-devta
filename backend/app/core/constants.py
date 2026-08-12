"""Small cross-layer constants that would otherwise need to be duplicated
(or force an import from `app.pricing` into `app.normalization`, which
would invert the intended dependency direction - normalization runs before
pricing, not the other way around)."""

HOURS_PER_MONTH = 730  # standard GCP billing convention (365 * 24 / 12)
