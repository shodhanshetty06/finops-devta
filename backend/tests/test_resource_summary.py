"""Focused tests for the per-resource quantity/subtotal behavior:
- every selected resource is calculated separately (resource name,
  quantity, unit cost, subtotal)
- identical service+configuration selections are merged into one row with
  a combined quantity, unit cost calculated once
- the same service with a different configuration gets its own row
- multiple different services each get their own row(s)
- the grand total across resource summaries equals the sum of their
  subtotals (and matches what the flat, already-existing line items/totals
  pipeline produces for the same selections)
"""
from app.catalog.generic_pricing import GenericServicePricingCalculator
from app.catalog.messaging_observability_pricing import MessagingObservabilityPricingCalculator
from app.catalog.resource_summary import build_resource_summaries
from app.domain.requirements import ServiceSelection
from app.pricing.mock_provider import MockGCPPricingProvider

CLOUD_RUN_CONFIG_A = {
    "requests_per_month": 1_000_000,
    "vcpu_seconds_per_month": 100_000,
    "gb_seconds_per_month": 100_000,
}
CLOUD_RUN_CONFIG_B = {
    "requests_per_month": 2_000_000,
    "vcpu_seconds_per_month": 200_000,
    "gb_seconds_per_month": 200_000,
}


def _build(selections):
    provider = MockGCPPricingProvider()
    generic = GenericServicePricingCalculator()
    messaging = MessagingObservabilityPricingCalculator()
    return build_resource_summaries(selections, generic, messaging, provider, provider.get_currency(), "us-central1")


def _unit_cost_of(config: dict) -> float:
    """Independently compute the cost of exactly one Cloud Run resource
    with this config, the same way the flat/existing pricing pipeline does,
    so tests never hardcode a pricing formula that could drift from
    app/catalog/generic_pricing.py."""
    calc = GenericServicePricingCalculator()
    line_items, _ = calc.calculate([ServiceSelection(service_id="cloud-run", config=config, quantity=1)], "USD")
    return round(sum(li.monthly_amount for li in line_items), 2)


def test_single_resource_has_name_quantity_unit_cost_and_subtotal():
    summaries = _build([ServiceSelection(service_id="cloud-run", config=CLOUD_RUN_CONFIG_A, quantity=1)])

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.resource_name == "Cloud Run"
    assert summary.quantity == 1
    assert summary.unit_cost == _unit_cost_of(CLOUD_RUN_CONFIG_A)
    assert summary.subtotal == summary.unit_cost


def test_identical_resource_times_quantity_is_priced_once_and_multiplied():
    # Cloud Run, 2 vCPU / 4 GB-equivalent config, quantity 4 - the example
    # from the spec: unit cost is calculated once, subtotal = unit cost x 4.
    summaries = _build([ServiceSelection(service_id="cloud-run", config=CLOUD_RUN_CONFIG_A, quantity=4)])

    assert len(summaries) == 1
    summary = summaries[0]
    unit_cost = _unit_cost_of(CLOUD_RUN_CONFIG_A)
    assert summary.quantity == 4
    assert summary.unit_cost == unit_cost
    assert summary.subtotal == round(unit_cost * 4, 2)


def test_same_service_different_configuration_gets_separate_rows():
    summaries = _build([
        ServiceSelection(service_id="cloud-run", config=CLOUD_RUN_CONFIG_A, quantity=2),
        ServiceSelection(service_id="cloud-run", config=CLOUD_RUN_CONFIG_B, quantity=1),
    ])

    assert len(summaries) == 2
    by_config = {s.configuration: s for s in summaries}
    unit_cost_a = _unit_cost_of(CLOUD_RUN_CONFIG_A)
    unit_cost_b = _unit_cost_of(CLOUD_RUN_CONFIG_B)

    a = next(s for s in summaries if s.quantity == 2)
    b = next(s for s in summaries if s.quantity == 1)
    assert a.unit_cost == unit_cost_a
    assert a.subtotal == round(unit_cost_a * 2, 2)
    assert b.unit_cost == unit_cost_b
    assert b.subtotal == unit_cost_b
    assert len(by_config) == 2  # distinct configuration strings, never merged


def test_duplicate_selections_with_the_same_config_are_merged_not_double_counted():
    # Two separate ServiceSelection entries (e.g. added via "Duplicate" in
    # the UI) with the same service + config sum their explicit quantities
    # into a single row rather than being priced/listed twice.
    summaries = _build([
        ServiceSelection(service_id="cloud-run", config=CLOUD_RUN_CONFIG_A, quantity=3),
        ServiceSelection(service_id="cloud-run", config=CLOUD_RUN_CONFIG_A, quantity=2),
    ])

    assert len(summaries) == 1
    summary = summaries[0]
    unit_cost = _unit_cost_of(CLOUD_RUN_CONFIG_A)
    assert summary.quantity == 5
    assert summary.unit_cost == unit_cost
    assert summary.subtotal == round(unit_cost * 5, 2)


def test_multiple_different_services_each_get_their_own_summary():
    summaries = _build([
        ServiceSelection(service_id="cloud-run", config=CLOUD_RUN_CONFIG_A, quantity=2),
        ServiceSelection(
            service_id="pubsub",
            config={"published_data_gb_per_day": 1, "subscriptions": 1},
            quantity=2,
        ),
        ServiceSelection(
            service_id="cloud-logging",
            config={"log_volume_gb_per_month": 80},
            quantity=4,
        ),
    ])

    names = {s.resource_name for s in summaries}
    assert names == {"Cloud Run", "Pub/Sub", "Cloud Logging"}

    pubsub = next(s for s in summaries if s.resource_name == "Pub/Sub")
    assert pubsub.quantity == 2
    assert pubsub.unit_cost == 1.95  # from test_messaging_observability_pricing.py's documented figure
    assert pubsub.subtotal == round(1.95 * 2, 2)

    logging_summary = next(s for s in summaries if s.resource_name == "Cloud Logging")
    assert logging_summary.quantity == 4
    assert logging_summary.unit_cost == 15.0  # (80 - 50 free GiB) * 0.50
    assert logging_summary.subtotal == round(15.0 * 4, 2)


def test_grand_total_equals_sum_of_all_resource_subtotals():
    selections = [
        ServiceSelection(service_id="cloud-run", config=CLOUD_RUN_CONFIG_A, quantity=4),
        ServiceSelection(service_id="cloud-run", config=CLOUD_RUN_CONFIG_B, quantity=1),
        ServiceSelection(service_id="pubsub", config={"published_data_gb_per_day": 1, "subscriptions": 1}, quantity=2),
    ]
    summaries = _build(selections)
    grand_total = round(sum(s.subtotal for s in summaries), 2)

    # Cross-check against the flat, already-existing line-item pipeline for
    # the same selections - the resource-summary grand total must match the
    # total the pricing engine would already compute from scaled line items.
    provider = MockGCPPricingProvider()
    generic = GenericServicePricingCalculator()
    messaging = MessagingObservabilityPricingCalculator()
    generic_items, _ = generic.calculate(selections, provider.get_currency())
    sku_items, _ = messaging.calculate(selections, provider, "us-central1")
    flat_total = round(sum(li.monthly_amount for li in generic_items + sku_items), 2)

    assert grand_total == flat_total
    assert grand_total == round(sum(s.subtotal for s in summaries), 2)
