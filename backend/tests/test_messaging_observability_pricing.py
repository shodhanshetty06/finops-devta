from app.catalog.messaging_observability_pricing import MessagingObservabilityPricingCalculator
from app.domain.requirements import ServiceSelection
from app.pricing.mock_provider import MockGCPPricingProvider


def _provider():
    return MockGCPPricingProvider()


def test_pubsub_prices_combined_publish_and_deliver_volume_minus_free_tier():
    # 1 GB/day published * 30 days = 30 GiB publish + 30 GiB deliver (1
    # subscription) = 60 GiB total, minus the 10 GiB/month free tier = 50
    # GiB billable, at $40/TiB (0.0390625/GiB) -> $1.95/month. This mirrors
    # the FinOps team's live customer worksheet for the same inputs.
    calc = MessagingObservabilityPricingCalculator()
    line_items, assumptions = calc.calculate(
        [ServiceSelection(service_id="pubsub", config={
            "published_data_gb_per_day": 1,
            "delivery_type": "basic",
            "topic_retention_days": 0,
            "subscriptions": 1,
            "subscriptions_with_retained_acks": 0,
            "ack_retention_window_days": 7,
            "snapshots_per_month": 0,
            "snapshot_retention_days": 0,
        })],
        _provider(), "us-central1",
    )
    assert len(line_items) == 1
    assert line_items[0].sku_id == "pubsub-message-delivery"
    assert line_items[0].monthly_amount == 1.95
    assert len(assumptions) == 1  # only the baseline pricing-method assumption; nothing unpriced was requested


def test_pubsub_more_subscriptions_multiplies_delivery_volume():
    calc = MessagingObservabilityPricingCalculator()
    line_items, _ = calc.calculate(
        [ServiceSelection(service_id="pubsub", config={"published_data_gb_per_day": 1, "subscriptions": 3})],
        _provider(), "us-central1",
    )
    # publish 30 GiB + deliver 30*3=90 GiB = 120 GiB total, minus 10 GiB free = 110 GiB billable
    assert line_items[0].quantity == 110.0
    assert line_items[0].monthly_amount == round(110 * (40 / 1024), 2)


def test_pubsub_under_free_tier_costs_nothing():
    calc = MessagingObservabilityPricingCalculator()
    line_items, _ = calc.calculate(
        [ServiceSelection(service_id="pubsub", config={"published_data_gb_per_day": 0.1, "subscriptions": 1})],
        _provider(), "us-central1",
    )
    # publish 3 GiB + deliver 3 GiB = 6 GiB total, well under the 10 GiB free tier
    assert line_items[0].monthly_amount == 0.0


def test_pubsub_flags_unpriced_dimensions_as_assumptions():
    calc = MessagingObservabilityPricingCalculator()
    _, assumptions = calc.calculate(
        [ServiceSelection(service_id="pubsub", config={
            "published_data_gb_per_day": 1,
            "delivery_type": "bigquery",
            "topic_retention_days": 30,
            "subscriptions_with_retained_acks": 2,
            "snapshots_per_month": 5,
        })],
        _provider(), "us-central1",
    )
    flagged_fields = {a.field for a in assumptions}
    assert "selected_services.pubsub.delivery_type" in flagged_fields
    assert "selected_services.pubsub.topic_retention_days" in flagged_fields
    assert "selected_services.pubsub.subscriptions_with_retained_acks" in flagged_fields
    assert "selected_services.pubsub.snapshots_per_month" in flagged_fields


def test_logging_prices_volume_minus_free_tier():
    calc = MessagingObservabilityPricingCalculator()
    line_items, assumptions = calc.calculate(
        [ServiceSelection(service_id="cloud-logging", config={"log_volume_gb_per_month": 30, "retention_days": 30})],
        _provider(), "us-central1",
    )
    assert len(line_items) == 1
    assert line_items[0].sku_id == "cloud-logging-volume"
    assert line_items[0].monthly_amount == 0.0  # 30 GiB is under the 50 GiB/month free tier
    assert len(assumptions) == 1


def test_logging_above_free_tier_is_billed():
    calc = MessagingObservabilityPricingCalculator()
    line_items, _ = calc.calculate(
        [ServiceSelection(service_id="cloud-logging", config={"log_volume_gb_per_month": 80})],
        _provider(), "us-central1",
    )
    assert line_items[0].monthly_amount == 15.0  # (80 - 50) * 0.50


def test_logging_flags_extended_retention_as_assumption():
    calc = MessagingObservabilityPricingCalculator()
    _, assumptions = calc.calculate(
        [ServiceSelection(service_id="cloud-logging", config={"log_volume_gb_per_month": 10, "retention_days": 90})],
        _provider(), "us-central1",
    )
    assert any(a.field == "selected_services.cloud-logging.retention_days" for a in assumptions)


def test_ignores_other_service_ids():
    calc = MessagingObservabilityPricingCalculator()
    line_items, assumptions = calc.calculate(
        [ServiceSelection(service_id="bigquery", config={"tb_scanned_per_month": 5})],
        _provider(), "us-central1",
    )
    assert line_items == [] and assumptions == []
