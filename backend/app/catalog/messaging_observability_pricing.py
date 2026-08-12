"""MessagingObservabilityPricingCalculator: prices Pub/Sub and Cloud Logging
service-catalog selections against a real `PricingProvider` (data-volume
pricing with the documented free tier each service actually has), instead of
`GenericServicePricingCalculator`'s flat `config_value / divisor * unit_price`
formula.

Google bills both of these services by data volume, not by the naive
per-unit counters (message count, raw GB with no free tier) a flat formula
implies, and both have a monthly free allowance a flat formula can't
express - pricing them generically was producing costs many times higher
than Google's own Pricing Calculator for the same inputs. Every other
catalog service with no dedicated pricing still goes through
`app/catalog/generic_pricing.py`; `PRICED_SERVICE_IDS` here is exactly the
set of service_ids this module owns instead, so the two calculators never
double-price (or double-emit assumptions for) the same selection.
"""
from app.domain.assumption import Assumption
from app.domain.pricing import CostLineItem
from app.domain.requirements import ServiceSelection
from app.pricing.base import PricingProvider

PRICED_SERVICE_IDS = {"pubsub", "cloud-logging"}

_DAYS_PER_MONTH = 30
# Indicative published rate for log storage retained beyond the free 30-day
# default (Cloud Logging custom bucket storage), same "never a live GCP
# Billing Catalog lookup, always indicative" caveat as generic_pricing.py.
_LOGGING_EXTENDED_RETENTION_PRICE_PER_GIB = 0.01


class MessagingObservabilityPricingCalculator:
    def calculate(
        self,
        selections: list[ServiceSelection],
        provider: PricingProvider,
        region: str,
    ) -> tuple[list[CostLineItem], list[Assumption]]:
        line_items: list[CostLineItem] = []
        assumptions: list[Assumption] = []

        for selection in selections:
            if selection.service_id == "pubsub":
                line_items += self._price_pubsub(selection, provider, region)
                assumptions += self._pubsub_assumptions(selection)
            elif selection.service_id == "cloud-logging":
                line_items += self._price_logging(selection, provider, region)
                assumptions += self._logging_assumptions(selection)

        return line_items, assumptions

    # -- Pub/Sub --------------------------------------------------------

    def _price_pubsub(self, selection: ServiceSelection, provider: PricingProvider, region: str) -> list[CostLineItem]:
        cfg = selection.config
        # Explicit resource count (e.g. 2 identical Pub/Sub topics) - the
        # unit cost (including the free tier) is calculated once, for one
        # topic, then multiplied by this, per user quantity.
        resource_quantity = max(selection.quantity, 1)
        published_gib_per_day = float(cfg.get("published_data_gb_per_day", 1) or 0)
        subscriptions = float(cfg.get("subscriptions", 1) or 0)

        publish_gib_per_month = published_gib_per_day * _DAYS_PER_MONTH
        # Basic delivery: each subscription independently pulls the full
        # published stream, so total delivery volume scales with subscription
        # count. (BigQuery-export subscriptions are billed the same way on
        # the Pub/Sub side - see the assumption raised when delivery_type is
        # "bigquery".)
        deliver_gib_per_month = publish_gib_per_month * subscriptions
        total_gib = publish_gib_per_month + deliver_gib_per_month

        free_tier_gib = provider.get_pubsub_free_tier_gib_per_month()
        billable_gib = max(0.0, total_gib - free_tier_gib)
        price_per_gib = provider.get_pubsub_price_per_gib(region)
        unit_monthly_amount = round(billable_gib * price_per_gib, 2)
        monthly_amount = round(unit_monthly_amount * resource_quantity, 2)
        total_billable_gib = billable_gib * resource_quantity

        description = (
            f"Pub/Sub Basic delivery: {publish_gib_per_month:,.1f} GiB published + "
            f"{deliver_gib_per_month:,.1f} GiB delivered across {subscriptions:.0f} subscription(s), "
            f"{free_tier_gib:,.0f} GiB/month free"
        )
        if resource_quantity != 1:
            description += f" (x{resource_quantity})"

        return [CostLineItem(
            category="Messaging & Eventing",
            description=description,
            sku_id="pubsub-message-delivery",
            unit="GiB",
            quantity=round(total_billable_gib, 4),
            unit_price=round(price_per_gib, 6),
            currency=provider.get_currency(),
            monthly_amount=monthly_amount,
            source=provider.source_name,
        )]

    def _pubsub_assumptions(self, selection: ServiceSelection) -> list[Assumption]:
        cfg = selection.config
        out = [Assumption(
            field="selected_services.pubsub",
            requested_value="Pub/Sub configuration",
            used_value="priced by combined publish+delivery data volume against a documented 10 GiB/month free tier",
            reason=(
                "Google bills Pub/Sub by data volume (publish + delivery), not by message count. "
                "Average message size is not part of the pricing formula itself - it only helps you "
                "translate a message-rate estimate into the published GB/day figure this form takes."
            ),
            strategy_applied="pubsub_throughput_pricing",
        )]
        if cfg.get("delivery_type") == "bigquery":
            out.append(Assumption(
                field="selected_services.pubsub.delivery_type",
                requested_value="bigquery",
                used_value="priced identically to Basic delivery",
                reason=(
                    "A BigQuery subscription incurs the same Pub/Sub delivery-volume charge as Basic, plus "
                    "separate BigQuery Storage Write API ingestion cost on the BigQuery side that this "
                    "calculator does not include - add a BigQuery line item separately for that portion."
                ),
                strategy_applied="pubsub_throughput_pricing",
            ))
        if float(cfg.get("topic_retention_days", 0) or 0) > 7:
            out.append(_not_priced(
                "selected_services.pubsub.topic_retention_days", cfg.get("topic_retention_days"),
                "Topic message retention beyond the free 7-day default incurs additional storage cost.",
                "pubsub_throughput_pricing",
            ))
        if float(cfg.get("subscriptions_with_retained_acks", 0) or 0) > 0:
            out.append(_not_priced(
                "selected_services.pubsub.subscriptions_with_retained_acks", cfg.get("subscriptions_with_retained_acks"),
                "Retaining acknowledged messages for replay/seek incurs additional storage cost.",
                "pubsub_throughput_pricing",
            ))
        if float(cfg.get("snapshots_per_month", 0) or 0) > 0:
            out.append(_not_priced(
                "selected_services.pubsub.snapshots_per_month", cfg.get("snapshots_per_month"),
                "Snapshots incur additional storage cost.",
                "pubsub_throughput_pricing",
            ))
        return out

    # -- Cloud Logging ----------------------------------------------------

    def _price_logging(self, selection: ServiceSelection, provider: PricingProvider, region: str) -> list[CostLineItem]:
        cfg = selection.config
        resource_quantity = max(selection.quantity, 1)
        volume_gib = float(cfg.get("log_volume_gb_per_month", 0) or 0)
        free_tier_gib = provider.get_logging_free_tier_gib_per_month()
        billable_gib = max(0.0, volume_gib - free_tier_gib)
        price_per_gib = provider.get_logging_price_per_gib(region)
        unit_monthly_amount = round(billable_gib * price_per_gib, 2)
        monthly_amount = round(unit_monthly_amount * resource_quantity, 2)
        total_billable_gib = billable_gib * resource_quantity

        description = f"Cloud Logging ingestion: {volume_gib:,.1f} GiB/month, {free_tier_gib:,.0f} GiB/month free"
        if resource_quantity != 1:
            description += f" (x{resource_quantity})"

        line_items = [CostLineItem(
            category="Observability",
            description=description,
            sku_id="cloud-logging-volume",
            unit="GiB",
            quantity=round(total_billable_gib, 4),
            unit_price=round(price_per_gib, 6),
            currency=provider.get_currency(),
            monthly_amount=monthly_amount,
            source=provider.source_name,
        )]

        extended_retention_gib = float(cfg.get("extended_retention_gb_per_month", 0) or 0)
        if extended_retention_gib > 0:
            retention_monthly_amount = round(extended_retention_gib * _LOGGING_EXTENDED_RETENTION_PRICE_PER_GIB * resource_quantity, 2)
            retention_description = f"Cloud Logging extended retention storage: {extended_retention_gib:,.1f} GiB/month beyond the free 30-day default"
            if resource_quantity != 1:
                retention_description += f" (x{resource_quantity})"
            line_items.append(CostLineItem(
                category="Observability",
                description=retention_description,
                sku_id="cloud-logging-extended-retention",
                unit="GiB",
                quantity=round(extended_retention_gib * resource_quantity, 4),
                unit_price=_LOGGING_EXTENDED_RETENTION_PRICE_PER_GIB,
                currency=provider.get_currency(),
                monthly_amount=retention_monthly_amount,
                source=provider.source_name,
            ))

        return line_items

    def _logging_assumptions(self, selection: ServiceSelection) -> list[Assumption]:
        out = [Assumption(
            field="selected_services.cloud-logging",
            requested_value="Cloud Logging configuration",
            used_value="priced by ingestion volume against a documented 50 GiB/month free tier",
            reason="Google bills Cloud Logging by ingested data volume, with the first 50 GiB/month free per project.",
            strategy_applied="logging_ingestion_pricing",
        )]
        retention_days = float(selection.config.get("retention_days", 30) or 30)
        extended_retention_gib = float(selection.config.get("extended_retention_gb_per_month", 0) or 0)
        if retention_days > 30 and extended_retention_gib <= 0:
            out.append(_not_priced(
                "selected_services.cloud-logging.retention_days", selection.config.get("retention_days"),
                "Extending log retention beyond the free 30-day default incurs additional storage cost - "
                "fill in 'Retained storage beyond 30 days (GB/month)' to price it.",
                "logging_ingestion_pricing",
            ))
        return out


def _not_priced(field: str, requested_value, reason: str, strategy: str) -> Assumption:
    return Assumption(
        field=field,
        requested_value=str(requested_value),
        used_value="not priced - not yet modeled in this calculator",
        reason=reason,
        strategy_applied=strategy,
    )
