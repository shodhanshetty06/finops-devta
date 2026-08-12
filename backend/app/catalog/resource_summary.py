"""Builds the resource-oriented cost view (Resource | Configuration |
Quantity | Unit Cost | Subtotal) for GCP-service-catalog selections
(app/domain/requirements.py::ServiceSelection).

Selections for the same service_id with the *same* pricing-relevant
configuration are merged into a single ResourceCostSummary row - the unit
cost is calculated once (by pricing exactly one instance of that config
through the same calculators app/catalog/generic_pricing.py and
app/catalog/messaging_observability_pricing.py already use for the flat
line-item ledger) and multiplied by the combined explicit quantity.
Selections for the same service with a different configuration always get
their own row. This never re-derives pricing logic - it only re-invokes the
existing calculators with quantity pinned to 1 to obtain a per-unit cost.
"""
import json

from app.catalog.generic_pricing import GenericServicePricingCalculator
from app.catalog.messaging_observability_pricing import MessagingObservabilityPricingCalculator
from app.catalog.service_definitions import SERVICE_CATALOG_BY_ID
from app.domain.assumption import Assumption
from app.domain.pricing import ResourceCostSummary
from app.domain.requirements import ServiceSelection
from app.pricing.base import PricingProvider


def _config_key(config: dict) -> str:
    return json.dumps(config, sort_keys=True, default=str)


def _describe_config(service_id: str, config: dict) -> str:
    definition = SERVICE_CATALOG_BY_ID.get(service_id)
    if not config:
        return "default configuration"
    schema_by_id = {f.field_id: f for f in definition.configuration_schema} if definition else {}
    parts = []
    for field_id, value in config.items():
        field = schema_by_id.get(field_id)
        label = field.label if field else field_id
        unit = f" {field.unit}" if field and field.unit else ""
        parts.append(f"{label}: {value}{unit}")
    return ", ".join(parts)


def build_resource_summaries(
    selections: list[ServiceSelection],
    generic_calculator: GenericServicePricingCalculator,
    messaging_calculator: MessagingObservabilityPricingCalculator,
    provider: PricingProvider,
    currency: str,
    region: str,
    assumptions: list[Assumption] | None = None,
) -> list[ResourceCostSummary]:
    groups: dict[tuple[str, str], dict] = {}
    order: list[tuple[str, str]] = []

    for selection in selections:
        key = (selection.service_id, _config_key(selection.config))
        if key not in groups:
            groups[key] = {"selection": selection, "quantity": 0}
            order.append(key)
        groups[key]["quantity"] += max(selection.quantity, 1)

    assumptions = assumptions or []

    summaries: list[ResourceCostSummary] = []
    for key in order:
        group = groups[key]
        selection: ServiceSelection = group["selection"]
        definition = SERVICE_CATALOG_BY_ID.get(selection.service_id)
        if definition is None:
            # Unknown/inactive service_id - GenericServicePricingCalculator
            # already records an Assumption for this; nothing priced to
            # summarize here.
            continue

        unit_selection = selection.model_copy(update={"quantity": 1})
        unit_line_items, _ = generic_calculator.calculate([unit_selection], currency)
        sku_line_items, _ = messaging_calculator.calculate([unit_selection], provider, region)
        priced_items = unit_line_items + sku_line_items
        unit_cost = round(sum(li.monthly_amount for li in priced_items), 2)

        quantity = group["quantity"]
        configuration = _describe_config(selection.service_id, selection.config)
        matching_assumptions = [
            a for a in assumptions if a.field == f"selected_services.{selection.service_id}"
        ]
        summaries.append(ResourceCostSummary(
            resource_name=definition.display_name,
            configuration=configuration,
            quantity=quantity,
            unit_cost=unit_cost,
            subtotal=round(unit_cost * quantity, 2),
            currency=currency,
            category=definition.category,
            sku_id=priced_items[0].sku_id if len(priced_items) == 1 else None,
            pricing_source=priced_items[0].source if priced_items else None,
            region=region,
            requested_configuration=configuration,
            normalized_configuration=configuration,
            status="assumption" if matching_assumptions else "valid",
            assumption_reason="; ".join(a.reason for a in matching_assumptions) or None,
        ))

    return summaries
