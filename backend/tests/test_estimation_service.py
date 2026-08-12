import pytest

from app.core.exceptions import ValidationFailedError
from app.domain.enums import GpuType, MachineFamily, Region
from app.domain.requirements import ComputeRequirement, CustomerRequirement, ServiceSelection
from app.pricing.engine import PricingEngine
from app.services.estimation_service import EstimationService


def make_service(catalog, pricing_provider, settings):
    return EstimationService(catalog=catalog, pricing_provider=pricing_provider, settings=settings)


def test_full_pipeline_produces_priced_estimate(catalog, pricing_provider, settings):
    service = make_service(catalog, pricing_provider, settings)
    req = CustomerRequirement(
        project_name="Acme Web App",
        region=Region.US_CENTRAL1,
        compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=3, ram_gb=10),
    )
    result = service.generate_estimate(req)

    assert result.normalized_spec.vcpu == 4  # balanced: 3 -> closer to 4? |3-2|=1,|3-4|=1 tie -> upward = 4
    assert result.cost.total_monthly > 0
    assert len(result.assumptions) >= 1
    assert len(result.audit_log.entries) > 0
    assert result.validation.blocker_count == 0


def test_pipeline_blocks_on_incompatible_gpu(catalog, pricing_provider, settings):
    service = make_service(catalog, pricing_provider, settings)
    req = CustomerRequirement(
        project_name="Bad GPU request",
        region=Region.US_CENTRAL1,
        compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16,
                                    gpu_type=GpuType.NVIDIA_A100_40GB, gpu_count=1),
    )
    with pytest.raises(ValidationFailedError):
        service.generate_estimate(req)


def test_force_overrides_blockers(catalog, pricing_provider, settings):
    service = make_service(catalog, pricing_provider, settings)
    req = CustomerRequirement(
        project_name="Bad GPU request forced",
        region=Region.US_CENTRAL1,
        compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16,
                                    gpu_type=GpuType.NVIDIA_A100_40GB, gpu_count=1),
    )
    result = service.generate_estimate(req, force=True)
    assert result.validation.blocker_count > 0
    assert result.cost.total_monthly > 0


def test_selected_services_mixes_bridged_and_generic_pricing(catalog, pricing_provider, settings):
    service = make_service(catalog, pricing_provider, settings)
    req = CustomerRequirement(
        project_name="Catalog-driven estimate",
        region=Region.US_CENTRAL1,
        compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16),
        selected_services=[
            ServiceSelection(service_id="persistent-disk", config={"disk_type": "pd-balanced", "size_gb": 100}),
            ServiceSelection(service_id="pubsub", config={"published_data_gb_per_day": 1, "subscriptions": 1}),
        ],
    )
    result = service.generate_estimate(req)

    # Bridged service (Persistent Disk -> StorageRequirement) went through
    # the real, existing PricingEngine/PricingProvider - assert it matches
    # calling that engine directly with the equivalent StorageRequirement.
    storage_items = [li for li in result.cost.line_items if li.category == "Storage" and li.sku_id and li.sku_id.startswith("disk-")]
    assert len(storage_items) == 1
    expected_disk_price = pricing_provider.get_disk_monthly_price_per_gb("pd-balanced", "us-central1")
    assert storage_items[0].monthly_amount == round(expected_disk_price * 100, 2)

    # Pub/Sub came from MessagingObservabilityPricingCalculator: 1 GB/day
    # published * 30 = 30 GiB publish + 30 GiB deliver (1 subscription) = 60
    # GiB total, minus the 10 GiB/month free tier = 50 GiB billable, at
    # $40/TiB (0.0390625/GiB).
    pubsub_items = [li for li in result.cost.line_items if li.sku_id == "pubsub-message-delivery"]
    assert len(pubsub_items) == 1
    assert pubsub_items[0].monthly_amount == 1.95

    # Both appear in architecture and both totals are folded into cost.total_monthly.
    services_in_architecture = {c.service for c in result.architecture.components}
    assert "Persistent Disk" in services_in_architecture
    assert "Pub/Sub" in services_in_architecture
    assert any(a.field == "selected_services.pubsub" for a in result.assumptions)
    assert result.cost.total_monthly > 0


def test_resource_summaries_reflect_quantity_and_grand_total(catalog, pricing_provider, settings):
    service = make_service(catalog, pricing_provider, settings)
    req = CustomerRequirement(
        project_name="Quantity-aware estimate",
        region=Region.US_CENTRAL1,
        compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16),
        selected_services=[
            ServiceSelection(
                service_id="cloud-run",
                config={"requests_per_month": 1_000_000, "vcpu_seconds_per_month": 100_000, "gb_seconds_per_month": 100_000},
                quantity=4,
            ),
            ServiceSelection(
                service_id="pubsub",
                config={"published_data_gb_per_day": 1, "subscriptions": 1},
                quantity=2,
            ),
        ],
    )
    result = service.generate_estimate(req)

    summaries = {s.resource_name: s for s in result.cost.resource_summaries}
    # Compute Engine (the legacy typed `compute` field) now also produces a
    # ResourceCostSummary row alongside the two catalog selections - see
    # app/catalog/legacy_resource_summary.py.
    assert set(summaries) == {"Cloud Run", "Pub/Sub", "Compute Engine"}

    cloud_run = summaries["Cloud Run"]
    assert cloud_run.quantity == 4
    assert cloud_run.subtotal == round(cloud_run.unit_cost * 4, 2)

    pubsub = summaries["Pub/Sub"]
    assert pubsub.quantity == 2
    assert pubsub.unit_cost == 1.95
    assert pubsub.subtotal == 3.9

    compute = summaries["Compute Engine"]
    assert compute.quantity == 1  # default instance_count
    assert compute.category == "Compute"
    assert compute.status == "valid"

    # Every resource's subtotal reconciles exactly with the pre-discount/
    # tax/support subtotal, and with the per-category rollup - the
    # SUM(resource subtotals) == SUM(category totals) == subtotal_monthly
    # invariant every estimate must satisfy (spec: no silent gap between
    # the resource-level view and the estimate total).
    resource_grand_total = round(sum(s.subtotal for s in result.cost.resource_summaries), 2)
    assert resource_grand_total == result.cost.subtotal_monthly
    assert round(sum(result.cost.category_totals.values()), 2) == result.cost.subtotal_monthly


def test_pricing_engine_extra_line_items_is_backward_compatible(pricing_provider, settings):
    # The new `extra_line_items` kwarg must be fully optional - existing call
    # sites that don't pass it must behave identically to before this change.
    from app.domain.estimate import NormalizedSpec
    from app.domain.requirements import CustomerRequirement as CR

    spec = NormalizedSpec(region="us-central1", machine_type="e2-standard-4", family="e2", vcpu=4, ram_gb=16, instance_count=1)
    req = CR(project_name="x", region=Region.US_CENTRAL1)
    engine = PricingEngine()
    cost = engine.calculate(spec, req, pricing_provider, settings)
    assert cost.total_monthly > 0


def test_business_only_request_triggers_ai_recommendation(catalog, pricing_provider, settings):
    from app.domain.requirements import BusinessContext
    service = make_service(catalog, pricing_provider, settings)
    req = CustomerRequirement(
        project_name="Business only",
        region=Region.US_CENTRAL1,
        business=BusinessContext(total_users=500, peak_concurrent_users=500),
    )
    result = service.generate_estimate(req)
    assert result.normalized_spec.machine_type is not None
    assert any(a.strategy_applied == "ai_recommendation" for a in result.assumptions)
    assert result.cost.total_monthly > 0
