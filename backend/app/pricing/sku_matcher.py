"""
Maps this platform's pricing concepts (machine family, region, disk type,
GPU type, Cloud SQL tier, ...) to specific SKUs returned by the Cloud
Billing Catalog API.

Google does not expose a machine-readable "this SKU is N2 vCPU pricing"
identifier. The only signals the API provides are a free-text
`description`, a `category` (serviceDisplayName / resourceFamily /
resourceGroup / usageType), and a `serviceRegions` list. This module's
matching strategy is deliberately split into two independent steps so each
can be reasoned about (and tested) on its own:

  1. Filter candidates by resourceFamily / usageType / description keywords
     - identifies *what* the SKU prices (e.g. "N2 vCPU", not "N2 RAM" or
     "N2 preemptible vCPU" or "N2 custom-machine-type vCPU", which are
     separate SKUs with separate prices).
  2. Narrow by `serviceRegions` containment - identifies *where* it applies.
     This is structured data, not text-parsing, and is the most reliable
     region signal the API provides, so region is never inferred from the
     description string.

Google's exact description strings are not part of any versioned contract
and can shift between launch cohorts. The keyword patterns below reflect
Google's publicly documented SKU description conventions (e.g. "N2 Instance
Core running in Americas", "Storage PD Capacity", "Nvidia Tesla T4 GPU
running in Americas"). Because this sandbox has no network path to Google
(see `docs/PHASE5_NOTES.md`), these patterns are verified against hand-built
fixtures shaped exactly like real API responses (`tests/test_sku_matcher.py`)
rather than the live endpoint. Re-verify against a live credential outside
this sandbox before relying on this for production invoicing-grade accuracy.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.exceptions import PricingProviderError
from app.pricing.gcp_client import GcpSku

# Google's Compute Engine SKU descriptions name families with these exact
# tokens (case preserved as Google publishes them; matching is
# case-insensitive so this is just for readability).
_FAMILY_KEYWORDS: dict[str, str] = {
    "e2": "E2",
    "n2": "N2",
    "n2d": "N2D",
    "c2": "Compute optimized",
    "a2": "A2",
}

_DISK_KEYWORDS: dict[str, str] = {
    "pd-standard": "Storage PD Capacity",
    "pd-balanced": "Balanced PD Capacity",
    "pd-ssd": "SSD backed PD Capacity",
    "pd-extreme": "Extreme PD Capacity",
}

_GPU_KEYWORDS: dict[str, str] = {
    "nvidia-tesla-t4": "Nvidia Tesla T4 GPU",
    "nvidia-l4": "Nvidia L4 GPU",
    "nvidia-tesla-a100": "Nvidia Tesla A100 GPU",
    "nvidia-tesla-v100": "Nvidia Tesla V100 GPU",
}

_OS_LICENSE_KEYWORDS: dict[str, str] = {
    "windows_server": "Windows Server",
    "rhel": "Red Hat Enterprise Linux",
    "suse": "SUSE Linux Enterprise Server",
}

_CUSTOM_SQL_TIER_RE = re.compile(r"^db-custom-(\d+)-(\d+)$")
_NAMED_SQL_TIER_KEYWORDS: dict[str, str] = {
    "db-f1-micro": "Micro",
    "db-g1-small": "Small",
}


def _region_matches(sku: GcpSku, region: str) -> bool:
    # Some SKUs (e.g. network egress-to-internet, certain management fees)
    # are not region-scoped and return an empty serviceRegions list - those
    # apply everywhere, so an empty list is treated as a match rather than
    # a non-match.
    if not sku.service_regions:
        return True
    return region in sku.service_regions


def _select_unique(candidates: list[GcpSku], what: str) -> GcpSku:
    if not candidates:
        raise PricingProviderError(
            f"No Cloud Billing Catalog SKU matched {what}. Google may have "
            f"renamed the SKU description, or the service account/API key's "
            f"billing account has no visibility into this SKU. This is a "
            f"configuration/mapping issue, not a transient failure - it will "
            f"not resolve on retry."
        )
    if len(candidates) == 1:
        return candidates[0]
    # More than one candidate survived filtering. This happens in practice
    # (Google sometimes publishes near-duplicate SKUs across sub-cohorts of
    # the same region). Deterministic tie-break: prefer the shortest
    # description, since the extra words on the longer variants are
    # consistently narrower qualifiers (e.g. a reservation-bound variant)
    # in Google's actual catalog - the canonical general-purpose SKU is
    # always the more concise description.
    return sorted(candidates, key=lambda s: len(s.description))[0]


def find_compute_core_sku(skus: list[GcpSku], family: str, region: str) -> GcpSku:
    keyword = _FAMILY_KEYWORDS.get(family)
    if keyword is None:
        raise PricingProviderError(f"No SKU matching rule configured for machine family '{family}'.")
    candidates = [
        s for s in skus
        if s.resource_family == "Compute"
        and s.usage_type == "OnDemand"
        and keyword.lower() in s.description.lower()
        and "core" in s.description.lower()
        and "custom" not in s.description.lower()  # custom machine types price separately
        and "sole tenancy" not in s.description.lower()
        and _region_matches(s, region)
    ]
    return _select_unique(candidates, f"compute vCPU ({family}, {region})")


def find_compute_ram_sku(skus: list[GcpSku], family: str, region: str) -> GcpSku:
    keyword = _FAMILY_KEYWORDS.get(family)
    if keyword is None:
        raise PricingProviderError(f"No SKU matching rule configured for machine family '{family}'.")
    candidates = [
        s for s in skus
        if s.resource_family == "Compute"
        and s.usage_type == "OnDemand"
        and keyword.lower() in s.description.lower()
        and "ram" in s.description.lower()
        and "custom" not in s.description.lower()
        and "sole tenancy" not in s.description.lower()
        and _region_matches(s, region)
    ]
    return _select_unique(candidates, f"compute RAM ({family}, {region})")


def find_disk_sku(skus: list[GcpSku], disk_type: str, region: str) -> GcpSku:
    keyword = _DISK_KEYWORDS.get(disk_type)
    if keyword is None:
        raise PricingProviderError(f"No SKU matching rule configured for disk type '{disk_type}'.")
    candidates = [
        s for s in skus
        if s.resource_family == "Storage"
        and keyword.lower() in s.description.lower()
        and "regional" not in s.description.lower()  # regional (replicated) PD is a distinct, pricier SKU
        and "snapshot" not in s.description.lower()
        and _region_matches(s, region)
    ]
    return _select_unique(candidates, f"persistent disk ({disk_type}, {region})")


def find_snapshot_sku(skus: list[GcpSku], region: str) -> GcpSku:
    candidates = [
        s for s in skus
        if s.resource_family == "Storage"
        and "snapshot" in s.description.lower()
        and "archive" not in s.description.lower()  # exclude Archive-class snapshot storage tier
        and _region_matches(s, region)
    ]
    return _select_unique(candidates, f"disk snapshot storage ({region})")


def find_gpu_sku(skus: list[GcpSku], gpu_type: str, region: str) -> GcpSku:
    keyword = _GPU_KEYWORDS.get(gpu_type)
    if keyword is None:
        raise PricingProviderError(f"No SKU matching rule configured for GPU type '{gpu_type}'.")
    candidates = [
        s for s in skus
        if s.resource_family in ("Compute", "GPU")
        and s.usage_type == "OnDemand"
        and keyword.lower() in s.description.lower()
        and _region_matches(s, region)
    ]
    return _select_unique(candidates, f"GPU ({gpu_type}, {region})")


def find_network_egress_sku(skus: list[GcpSku], region: str) -> GcpSku:
    # Verified against a real Cloud Billing Catalog API response
    # (2026-08-12): Google's current SKU description reads "Standard Data
    # Transfer Out to Internet from <city>" - it never uses the word
    # "egress" and the tier qualifier is "Standard" (Premium Tier's
    # equivalent SKU uses a different description entirely, so it never
    # matches this filter and needs no separate exclusion).
    candidates = [
        s for s in skus
        if s.resource_family == "Network"
        and "data transfer out to internet" in s.description.lower()
        and "standard" in s.description.lower()
        and "vpn" not in s.description.lower()
        and _region_matches(s, region)
    ]
    return _select_unique(candidates, f"network egress ({region})")


def find_os_license_sku(skus: list[GcpSku], operating_system: str) -> GcpSku:
    # OS licensing fees are global (Google does not vary Windows/RHEL/SUSE
    # per-vCPU licensing by region), so no `_region_matches` filter here -
    # matches the same reasoning `find_pubsub_message_delivery_sku` and
    # `find_logging_volume_sku` already use for their own global SKUs.
    keyword = _OS_LICENSE_KEYWORDS.get(operating_system)
    if keyword is None:
        raise PricingProviderError(f"No SKU matching rule configured for operating system '{operating_system}'.")
    candidates = [
        s for s in skus
        if s.resource_family == "Licensing"
        and keyword.lower() in s.description.lower()
    ]
    return _select_unique(candidates, f"OS licensing ({operating_system})")


def find_local_ssd_sku(skus: list[GcpSku], region: str) -> GcpSku:
    candidates = [
        s for s in skus
        if s.resource_family == "Storage"
        and "ssd backed local storage" in s.description.lower()
        and _region_matches(s, region)
    ]
    return _select_unique(candidates, f"Local SSD ({region})")


def find_static_ip_sku(skus: list[GcpSku], region: str) -> GcpSku:
    candidates = [
        s for s in skus
        if s.resource_family == "Network"
        and "static ip charge" in s.description.lower()
        and _region_matches(s, region)
    ]
    return _select_unique(candidates, f"static IP address ({region})")


def find_load_balancer_sku(skus: list[GcpSku], region: str) -> GcpSku:
    candidates = [
        s for s in skus
        if s.resource_family == "Network"
        and "forwarding rule" in s.description.lower()
        and _region_matches(s, region)
    ]
    return _select_unique(candidates, f"load balancer forwarding rule ({region})")


def find_pubsub_message_delivery_sku(skus: list[GcpSku]) -> GcpSku:
    # Pub/Sub Basic tier bills combined publish + delivery data volume under
    # a single "Message Delivery Basic" SKU that is global (no service
    # region restriction), per Google's published Pub/Sub pricing page.
    candidates = [
        s for s in skus
        if "message delivery" in s.description.lower()
        and "basic" in s.description.lower()
    ]
    return _select_unique(candidates, "Pub/Sub message delivery (Basic tier)")


def find_logging_volume_sku(skus: list[GcpSku]) -> GcpSku:
    # Cloud Logging ingestion is billed under a single global "Log Volume"
    # SKU (no service region restriction), per Google's published Cloud
    # Logging pricing page.
    candidates = [
        s for s in skus
        if "log volume" in s.description.lower()
    ]
    return _select_unique(candidates, "Cloud Logging ingestion volume")


def find_gke_management_sku(skus: list[GcpSku], *, autopilot: bool) -> GcpSku:
    # Verified against a real Cloud Billing Catalog API response
    # (2026-08-12): Google's current SKU descriptions are "Zonal Kubernetes
    # Clusters" / "Regional Kubernetes Clusters" / "Autopilot Kubernetes
    # Clusters" - there is no "cluster management" wording, and each is a
    # single global (non region-scoped) SKU, matching this provider's
    # `get_gke_cluster_management_hourly_price(autopilot)` signature (no
    # region parameter). Standard mode matches the Zonal SKU - the cheaper,
    # more common topology - since this method doesn't distinguish
    # zonal/regional; documented here as a simplification, same status as
    # the flat CUD/SUD discount percentages this provider already uses
    # elsewhere (see gcp_provider.py's module docstring).
    keyword = "autopilot kubernetes clusters" if autopilot else "zonal kubernetes clusters"
    candidates = [s for s in skus if s.description.lower() == keyword]
    return _select_unique(candidates, f"GKE cluster management fee (autopilot={autopilot})")


@dataclass(frozen=True)
class CloudSqlTierShape:
    """Cloud SQL tiers in this platform's requirement model are either a
    named tier ("db-f1-micro") or a custom shape ("db-custom-<vcpu>-<mb>").
    Google prices Cloud SQL the same way it prices Compute Engine: separate
    per-vCPU and per-GB-RAM SKUs, summed. This dataclass carries the parsed
    shape so the caller can decide whether it needs one SKU lookup (named
    tier - Google publishes a single flat SKU for f1-micro/g1-small) or two
    (custom shape - vCPU and RAM priced independently)."""

    is_custom: bool
    vcpu: int | None = None
    ram_mb: int | None = None
    named_keyword: str | None = None


def parse_cloud_sql_tier(tier: str) -> CloudSqlTierShape:
    if tier in _NAMED_SQL_TIER_KEYWORDS:
        return CloudSqlTierShape(is_custom=False, named_keyword=_NAMED_SQL_TIER_KEYWORDS[tier])
    match = _CUSTOM_SQL_TIER_RE.match(tier)
    if match:
        return CloudSqlTierShape(is_custom=True, vcpu=int(match.group(1)), ram_mb=int(match.group(2)))
    raise PricingProviderError(
        f"Cloud SQL tier '{tier}' is not a recognized named tier or "
        f"'db-custom-<vcpu>-<ram_mb>' shape."
    )


def find_cloud_sql_named_tier_sku(skus: list[GcpSku], tier: str, region: str) -> GcpSku:
    shape = parse_cloud_sql_tier(tier)
    if shape.is_custom:
        raise PricingProviderError(f"'{tier}' is a custom tier; use find_cloud_sql_core_sku/find_cloud_sql_ram_sku instead.")
    candidates = [
        s for s in skus
        if s.resource_family == "ApplicationServices"
        and s.service_display_name == "Cloud SQL"
        and shape.named_keyword.lower() in s.description.lower()
        and _region_matches(s, region)
    ]
    return _select_unique(candidates, f"Cloud SQL named tier ({tier}, {region})")


def find_cloud_sql_core_sku(skus: list[GcpSku], region: str) -> GcpSku:
    candidates = [
        s for s in skus
        if s.resource_family == "ApplicationServices"
        and s.service_display_name == "Cloud SQL"
        and "cpu" in s.description.lower()
        and _region_matches(s, region)
    ]
    return _select_unique(candidates, f"Cloud SQL custom vCPU ({region})")


def find_cloud_sql_ram_sku(skus: list[GcpSku], region: str) -> GcpSku:
    candidates = [
        s for s in skus
        if s.resource_family == "ApplicationServices"
        and s.service_display_name == "Cloud SQL"
        and "ram" in s.description.lower()
        and _region_matches(s, region)
    ]
    return _select_unique(candidates, f"Cloud SQL custom RAM ({region})")


def find_cloud_sql_storage_sku(skus: list[GcpSku], region: str) -> GcpSku:
    candidates = [
        s for s in skus
        if s.resource_family == "ApplicationServices"
        and s.service_display_name == "Cloud SQL"
        and "storage" in s.description.lower()
        and "ssd" in s.description.lower()
        and _region_matches(s, region)
    ]
    return _select_unique(candidates, f"Cloud SQL SSD storage ({region})")


def find_cloud_sql_backup_storage_sku(skus: list[GcpSku], region: str) -> GcpSku:
    """Also used for binary log storage - Google bills both under the same
    backup-storage SKU, so callers price binary_log_storage_gb through this
    same lookup rather than a separate one."""
    candidates = [
        s for s in skus
        if s.resource_family == "ApplicationServices"
        and s.service_display_name == "Cloud SQL"
        and "backup" in s.description.lower()
        and _region_matches(s, region)
    ]
    return _select_unique(candidates, f"Cloud SQL backup storage ({region})")


def find_disk_provisioned_iops_sku(skus: list[GcpSku], region: str) -> GcpSku:
    candidates = [
        s for s in skus
        if s.resource_family == "Storage"
        and "iops" in s.description.lower()
        and "extreme" in s.description.lower()
        and _region_matches(s, region)
    ]
    return _select_unique(candidates, f"Extreme PD provisioned IOPS ({region})")


def find_disk_provisioned_throughput_sku(skus: list[GcpSku], region: str) -> GcpSku:
    candidates = [
        s for s in skus
        if s.resource_family == "Storage"
        and "throughput" in s.description.lower()
        and _region_matches(s, region)
    ]
    return _select_unique(candidates, f"provisioned disk throughput ({region})")
