"""
Live verification script for Phase 5 (see docs/PHASE5_LIVE_VERIFICATION.md).

Run from `backend/` with FINOPS_PRICING_PROVIDER=gcp and either
FINOPS_GCP_SERVICE_ACCOUNT_JSON or FINOPS_GCP_API_KEY set:

    python -m scripts.verify_gcp_pricing
    python -m scripts.verify_gcp_pricing --dump-skus "Compute Engine"

This makes real calls to the Cloud Billing Catalog API - it is deliberately
NOT part of the pytest suite (which must stay offline/deterministic). It
exists purely so a human can confirm, once, that the SKU-matching keyword
patterns in `app/pricing/sku_matcher.py` still line up with what Google's
API actually returns today.
"""
import argparse
import sys

from app.core.config import get_settings
from app.core.exceptions import PricingProviderError
from app.pricing.cache import get_sku_cache
from app.pricing.gcp_client import CloudBillingCatalogClient
from app.pricing.gcp_provider import GcpPricingProvider

_CHECKS = [
    ("N2 compute, us-central1 (4 vCPU / 16 GB)", lambda p: p.get_compute_hourly_price_for_spec(4, 16, "n2", "us-central1")),
    ("E2 compute, us-central1 (2 vCPU / 8 GB)", lambda p: p.get_compute_hourly_price_for_spec(2, 8, "e2", "us-central1")),
    ("pd-ssd disk, us-central1 (per GB/month)", lambda p: p.get_disk_monthly_price_per_gb("pd-ssd", "us-central1")),
    ("nvidia-tesla-t4 GPU, us-central1 (hourly)", lambda p: p.get_gpu_hourly_price("nvidia-tesla-t4", "us-central1")),
    ("Cloud SQL db-f1-micro, us-central1 (hourly)", lambda p: p.get_cloud_sql_hourly_price("db-f1-micro", "us-central1")),
    ("Network egress, us-central1 (per GB)", lambda p: p.get_network_egress_price_per_gb("us-central1")),
    ("GKE standard cluster management (hourly)", lambda p: p.get_gke_cluster_management_hourly_price(autopilot=False)),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump-skus", metavar="SERVICE_DISPLAY_NAME",
                         help='e.g. "Compute Engine" - prints every SKU description for that service and exits.')
    args = parser.parse_args()

    settings = get_settings()
    if settings.pricing_provider != "gcp":
        print("FINOPS_PRICING_PROVIDER is not set to 'gcp'. Set it and re-run.", file=sys.stderr)
        return 1

    client = CloudBillingCatalogClient.from_settings(settings)

    if args.dump_skus:
        service = client.find_service(args.dump_skus)
        skus = client.list_skus(service.service_id, currency_code=settings.default_currency)
        print(f"{len(skus)} SKUs for '{args.dump_skus}':")
        for sku in skus:
            print(f"  [{sku.usage_type:12s}] {sku.description}")
        return 0

    provider = GcpPricingProvider(client, get_sku_cache(), settings)
    failures = 0
    for label, check in _CHECKS:
        try:
            price = check(provider)
            print(f"OK    {label}: {settings.default_currency} {price:.6f}")
        except PricingProviderError as exc:
            failures += 1
            print(f"FAIL  {label}: {exc}")
    provider.close()

    if failures:
        print(f"\n{failures} of {len(_CHECKS)} checks failed - see docs/PHASE5_LIVE_VERIFICATION.md step 4.")
        return 1
    print(f"\nAll {len(_CHECKS)} checks passed - live GCP pricing is confirmed end-to-end.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
