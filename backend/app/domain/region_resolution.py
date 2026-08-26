"""
Single authoritative place the backend decides which GCP region to price
against. Every entry point that can name a region - the Quick Estimate form,
a parsed/AI-extracted workbook, or nothing at all - funnels through this one
function, so the priority order (explicit user choice > region found in the
workbook > application default) is enforced exactly once, in one place, on
the backend - not duplicated as ad-hoc fallback logic in each caller
(including the frontend).
"""
from __future__ import annotations

from app.core.exceptions import FinOpsError
from app.domain.enums import Region

# The org's primary region. Used whenever neither the user nor the uploaded
# workbook names one. A plain code constant, not a Settings field - nothing
# today needs this configurable per-deployment; promote it to
# Settings.default_region if that ever changes.
DEFAULT_REGION = Region.ASIA_SOUTH1

RegionSource = str  # "selected" | "workbook" | "default"


def resolve_region(
    user_override: str | None,
    workbook_region: str | None,
    configured_default: Region = DEFAULT_REGION,
) -> tuple[Region, RegionSource]:
    """Returns (resolved_region, source). `source` tells the caller which of
    the three inputs won, so the UI can honestly label where the region came
    from (see Phase 3 of the region-handling fix) instead of always claiming
    "from workbook" even when nothing was actually parsed.

    Both `user_override` and `workbook_region`, when non-empty, must already
    be valid `Region` values - an unsupported string is rejected with a
    clear error rather than silently discarded, since silently falling
    through to the default would price a different region than the one the
    caller actually named.
    """
    for source, candidate in (("selected", user_override), ("workbook", workbook_region)):
        if not candidate:
            continue
        try:
            return Region(candidate), source
        except ValueError:
            raise FinOpsError(
                f"'{candidate}' is not a supported GCP region.", code="invalid_region",
            )
    return configured_default, "default"
