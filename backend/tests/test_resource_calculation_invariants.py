"""Cross-cutting resource-calculation invariant tests for the generalized
Resource -> Quantity -> Unit Cost -> Subtotal -> Category Total -> Grand
Total model (app/catalog/legacy_resource_summary.py +
app/catalog/resource_summary.py, wired together in
EstimationService.generate_estimate). Complements test_resource_summary.py
(catalog-selections-only) by covering the legacy typed resources (Compute
Engine, Persistent Disk, Cloud SQL, Networking, GKE) and the combined
reconciliation invariant across both paths.
"""
from app.domain.enums import DiskType, MachineFamily, Region
from app.domain.requirements import (
    ComputeRequirement,
    CustomerRequirement,
    DatabaseRequirement,
    NetworkRequirement,
    ServiceSelection,
    StorageRequirement,
)
from app.services.estimation_service import EstimationService


def make_service(catalog, pricing_provider, settings):
    return EstimationService(catalog=catalog, pricing_provider=pricing_provider, settings=settings)


def _assert_reconciles(cost):
    """The invariant every estimate must satisfy: the resource-level view,
    the category rollup, and the pre-discount/tax/support subtotal always
    agree exactly - there is never a silent gap between them."""
    resource_total = round(sum(r.subtotal for r in cost.resource_summaries), 2)
    category_total = round(sum(cost.category_totals.values()), 2)
    assert resource_total == cost.subtotal_monthly
    assert category_total == cost.subtotal_monthly


def test_single_legacy_resource_has_quantity_unit_cost_and_subtotal(catalog, pricing_provider, settings):
    service = make_service(catalog, pricing_provider, settings)
    req = CustomerRequirement(
        project_name="Single VM",
        region=Region.US_CENTRAL1,
        compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16, instance_count=1),
    )
    result = service.generate_estimate(req)

    assert len(result.cost.resource_summaries) == 1
    compute = result.cost.resource_summaries[0]
    assert compute.resource_name == "Compute Engine"
    assert compute.quantity == 1
    assert compute.category == "Compute"
    assert compute.subtotal == round(compute.unit_cost * 1, 2)
    _assert_reconciles(result.cost)


def test_identical_legacy_configuration_times_instance_count_is_one_row(catalog, pricing_provider, settings):
    service = make_service(catalog, pricing_provider, settings)
    req = CustomerRequirement(
        project_name="Fleet of identical VMs",
        region=Region.US_CENTRAL1,
        compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16, instance_count=5),
    )
    result = service.generate_estimate(req)

    compute = next(r for r in result.cost.resource_summaries if r.resource_name == "Compute Engine")
    assert compute.quantity == 5
    assert compute.subtotal == round(compute.unit_cost * 5, 2)
    _assert_reconciles(result.cost)


def test_multiple_legacy_resource_types_each_get_their_own_row_and_category(catalog, pricing_provider, settings):
    service = make_service(catalog, pricing_provider, settings)
    req = CustomerRequirement(
        project_name="Multi-resource, multi-category estimate",
        region=Region.US_CENTRAL1,
        compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16, instance_count=2),
        storage=StorageRequirement(disk_type=DiskType.PD_BALANCED, size_gb=200),
        database=DatabaseRequirement(required=True, vcpu=2, ram_gb=8, size_gb=100),
        network=NetworkRequirement(external_ip_count=1, estimated_egress_gb_per_month=50),
        selected_services=[
            ServiceSelection(
                service_id="pubsub",
                config={"published_data_gb_per_day": 1, "subscriptions": 1},
                quantity=2,
            ),
        ],
    )
    result = service.generate_estimate(req)

    names = {r.resource_name for r in result.cost.resource_summaries}
    assert names == {"Compute Engine", "Persistent Disk", "Cloud SQL", "Networking", "Pub/Sub"}

    categories = {r.category for r in result.cost.resource_summaries}
    assert categories == {"Compute", "Storage", "Database", "Network", "Messaging & Eventing"}

    assert set(result.cost.category_totals) == categories
    _assert_reconciles(result.cost)


def test_normalized_legacy_resource_reports_status_and_reason(catalog, pricing_provider, settings):
    service = make_service(catalog, pricing_provider, settings)
    req = CustomerRequirement(
        project_name="Unsupported vCPU count",
        region=Region.US_CENTRAL1,
        # 3 vCPU does not exist in the e2 family (mock catalog) - forces a
        # normalization substitution, same scenario as
        # test_estimation_service.py::test_full_pipeline_produces_priced_estimate.
        compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=3, ram_gb=10),
    )
    result = service.generate_estimate(req)

    compute = next(r for r in result.cost.resource_summaries if r.resource_name == "Compute Engine")
    assert compute.status == "normalized"
    assert compute.assumption_reason
    assert compute.requested_configuration != compute.normalized_configuration
    assert "3" in compute.requested_configuration
    _assert_reconciles(result.cost)


def test_grand_total_reconciles_across_legacy_and_catalog_resources(catalog, pricing_provider, settings):
    service = make_service(catalog, pricing_provider, settings)
    req = CustomerRequirement(
        project_name="Reconciliation check",
        region=Region.US_CENTRAL1,
        compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16, instance_count=3),
        selected_services=[
            ServiceSelection(
                service_id="cloud-run",
                config={"requests_per_month": 1_000_000, "vcpu_seconds_per_month": 100_000, "gb_seconds_per_month": 100_000},
                quantity=4,
            ),
            ServiceSelection(
                service_id="cloud-run",
                config={"requests_per_month": 2_000_000, "vcpu_seconds_per_month": 200_000, "gb_seconds_per_month": 200_000},
                quantity=2,
            ),
        ],
    )
    result = service.generate_estimate(req)

    cloud_run_rows = [r for r in result.cost.resource_summaries if r.resource_name == "Cloud Run"]
    assert len(cloud_run_rows) == 2  # different configs never merged (spec: no blind multiplication)
    _assert_reconciles(result.cost)

    # Total monthly still applies discounts/tax/support on top of the
    # reconciled subtotal - it is not expected to equal the raw resource
    # sum, since those adjustments are estimate-wide, not per-resource.
    assert result.cost.total_monthly >= result.cost.subtotal_monthly - result.cost.discount_total_monthly
