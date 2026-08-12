from app.catalog.generic_pricing import GenericServicePricingCalculator
from app.domain.requirements import ServiceSelection


def _calc():
    return GenericServicePricingCalculator()


def test_default_quantity_of_one_matches_previous_unscaled_behavior():
    line_items, _ = _calc().calculate(
        [ServiceSelection(service_id="bigquery", config={"tb_scanned_per_month": 2, "active_storage_gb": 100})],
        "USD",
    )
    query_item = next(li for li in line_items if li.sku_id == "bigquery-query")
    assert query_item.quantity == 2
    assert query_item.unit_price == 6.25
    assert query_item.monthly_amount == 12.5
    assert "x" not in query_item.description.split("—")[-1]  # no "(xN)" suffix at quantity 1


def test_explicit_quantity_multiplies_every_pricing_dimension():
    line_items, _ = _calc().calculate(
        [ServiceSelection(
            service_id="bigquery",
            config={"tb_scanned_per_month": 2, "active_storage_gb": 100},
            quantity=3,
        )],
        "USD",
    )
    query_item = next(li for li in line_items if li.sku_id == "bigquery-query")
    storage_item = next(li for li in line_items if li.sku_id == "bigquery-storage")

    # Unit price (the per-TB / per-GB rate) never changes with quantity -
    # only the total quantity purchased and the resulting monthly amount do.
    assert query_item.unit_price == 6.25
    assert query_item.quantity == 6  # 2 TB x 3
    assert query_item.monthly_amount == 37.5  # 12.5 x 3
    assert "(x3)" in query_item.description

    assert storage_item.unit_price == 0.02
    assert storage_item.quantity == 300  # 100 GB x 3
    assert storage_item.monthly_amount == 6.0  # 2.0 x 3


def test_unit_cost_times_quantity_equals_monthly_amount_invariant():
    for quantity in (1, 2, 5):
        line_items, _ = _calc().calculate(
            [ServiceSelection(service_id="bigquery", config={"tb_scanned_per_month": 1}, quantity=quantity)],
            "USD",
        )
        item = next(li for li in line_items if li.sku_id == "bigquery-query")
        assert round(item.unit_price * item.quantity, 2) == item.monthly_amount


def test_cloud_cdn_and_vpn_now_price_above_zero():
    """Regression test: Cloud CDN and VPN used to be bound to the legacy
    NetworkRequirement path, which never actually priced cdn_enabled/
    vpn_required, so selecting them cost $0. They're now priced generically."""
    cdn_items, _ = _calc().calculate(
        [ServiceSelection(service_id="cloud-cdn", config={
            "cache_egress_gb_per_month": 500, "invalidation_requests_per_month": 100,
            "cache_lookup_requests_per_month": 50_000,
        })],
        "USD",
    )
    assert sum(li.monthly_amount for li in cdn_items) > 0

    vpn_items, _ = _calc().calculate(
        [ServiceSelection(service_id="vpn", config={"tunnels": 2, "data_egress_gb_per_month": 200})],
        "USD",
    )
    assert sum(li.monthly_amount for li in vpn_items) > 0


def test_load_balancing_rate_by_option_varies_by_lb_type():
    global_items, _ = _calc().calculate(
        [ServiceSelection(service_id="load-balancing", config={"lb_type": "global_https", "forwarding_rules": 1})],
        "USD",
    )
    internal_items, _ = _calc().calculate(
        [ServiceSelection(service_id="load-balancing", config={"lb_type": "internal", "forwarding_rules": 1})],
        "USD",
    )
    global_base = next(li for li in global_items if li.sku_id == "load-balancing-base-fee")
    internal_base = next(li for li in internal_items if li.sku_id == "load-balancing-base-fee")
    assert global_base.monthly_amount > 0
    assert internal_base.monthly_amount == 0


def test_dataproc_derives_vcpu_hours_from_cluster_spec():
    line_items, _ = _calc().calculate(
        [ServiceSelection(service_id="dataproc", config={"node_vcpu": 4, "node_count": 3, "cluster_hours_per_month": 100})],
        "USD",
    )
    item = next(li for li in line_items if li.sku_id == "dataproc-vcpu-hours")
    assert item.quantity == 4 * 3 * 100
    assert item.monthly_amount == round(4 * 3 * 100 * 0.01, 2)


def test_bigquery_on_demand_and_editions_are_mutually_exclusive_by_input():
    on_demand_items, _ = _calc().calculate(
        [ServiceSelection(service_id="bigquery", config={"pricing_model": "on_demand", "tb_scanned_per_month": 10})],
        "USD",
    )
    on_demand_slots = next(li for li in on_demand_items if li.sku_id == "bigquery-slots")
    assert on_demand_slots.monthly_amount == 0

    editions_items, _ = _calc().calculate(
        [ServiceSelection(service_id="bigquery", config={"pricing_model": "enterprise_edition", "slots_provisioned": 100})],
        "USD",
    )
    editions_query = next(li for li in editions_items if li.sku_id == "bigquery-query")
    editions_slots = next(li for li in editions_items if li.sku_id == "bigquery-slots")
    assert editions_query.monthly_amount == 0
    assert editions_slots.monthly_amount == 100 * 43.80
