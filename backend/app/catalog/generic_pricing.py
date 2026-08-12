"""GenericServicePricingCalculator: prices any catalog service that has no
dedicated PricingProvider method (i.e. everything except the handful of
services bridged into the legacy schema by service_catalog_bridge.py).

Deliberately simple and fully data-driven: for each selected service, for
each declared PricingDimension, `monthly_amount = (config_value /
quantity_divisor) * unit_price_usd`. Adding a new priced service never
touches this file - only app/catalog/service_definitions.py.

Because this uses indicative public list pricing rather than a live GCP
Billing Catalog lookup (unlike PricingEngine, which always delegates to a
PricingProvider), every priced service also gets an Assumption recorded so
the estimate never silently presents an approximation as exact - the same
"never silently change/estimate a customer's request" principle the
normalization engine already follows for Assumption logging.
"""
from app.catalog.messaging_observability_pricing import PRICED_SERVICE_IDS as _SKU_PRICED_SERVICE_IDS
from app.catalog.service_catalog import GCPServiceDefinition, PricingDimension
from app.catalog.service_catalog_derivations import apply_computed_fields
from app.catalog.service_definitions import SERVICE_CATALOG_BY_ID
from app.domain.assumption import Assumption
from app.domain.pricing import CostLineItem
from app.domain.requirements import ServiceSelection
from app.pricing.mock_data import REGION_MULTIPLIER

SOURCE_NAME = "generic_service_catalog_estimate"


def _region_multiplier(config: dict) -> float:
    region = config.get("region")
    return REGION_MULTIPLIER.get(region, 1.0) if region else 1.0


def _effective_unit_price(dimension: PricingDimension, config: dict) -> float:
    if dimension.rate_selector_field_id and dimension.rate_by_option:
        selected = config.get(dimension.rate_selector_field_id)
        selected_key = str(selected).lower() if isinstance(selected, bool) else selected
        if selected_key in dimension.rate_by_option:
            return dimension.rate_by_option[selected_key]
    return dimension.unit_price_usd


def _field_default(definition: GCPServiceDefinition, field_id: str):
    for field in definition.configuration_schema:
        if field.field_id == field_id:
            return field.default
    return None


class GenericServicePricingCalculator:
    def calculate(
        self,
        selections: list[ServiceSelection],
        currency: str,
    ) -> tuple[list[CostLineItem], list[Assumption]]:
        line_items: list[CostLineItem] = []
        assumptions: list[Assumption] = []

        for selection in selections:
            if selection.service_id in _SKU_PRICED_SERVICE_IDS:
                # Priced separately by MessagingObservabilityPricingCalculator
                # (data-volume + free-tier model) - skip silently so it isn't
                # double-priced or double-recorded as an assumption here.
                continue

            definition = SERVICE_CATALOG_BY_ID.get(selection.service_id)
            if definition is None or not definition.active:
                assumptions.append(Assumption(
                    field=f"selected_services.{selection.service_id}",
                    requested_value=selection.service_id,
                    used_value="skipped - not in catalog",
                    reason=f"'{selection.service_id}' is not a known active service in the GCP service catalog; it was not priced.",
                    strategy_applied="generic_service_catalog",
                ))
                continue

            if not definition.pricing_dimensions:
                assumptions.append(Assumption(
                    field=f"selected_services.{selection.service_id}",
                    requested_value=definition.display_name,
                    used_value="no cost added",
                    reason=f"{definition.display_name} has no priced dimensions defined in the catalog yet.",
                    strategy_applied="generic_service_catalog",
                ))
                continue

            # Explicit resource count (e.g. 4 identical Cloud Run services) -
            # never inferred from the request, always what the user entered
            # on this selection (default 1). Each dimension is priced for
            # one unit first, then scaled, so `unit_price * quantity ==
            # monthly_amount` keeps holding for the resulting line item.
            resource_quantity = max(selection.quantity, 1)
            # Fills in derived quantities (e.g. Cloud Run's billable
            # vCPU-seconds) from the raw fields the customer actually
            # entered - see service_catalog_derivations.py. A no-op dict
            # copy for every service that has no derivation registered.
            config = apply_computed_fields(selection.service_id, selection.config)
            region_multiplier = _region_multiplier(config)
            for dimension in definition.pricing_dimensions:
                raw_value = config.get(dimension.config_field_id)
                if raw_value is None:
                    raw_value = _field_default(definition, dimension.config_field_id) or 0
                effective_unit_price = _effective_unit_price(dimension, config) * region_multiplier
                unit_quantity = float(raw_value) / dimension.quantity_divisor
                unit_monthly_amount = unit_quantity * effective_unit_price
                total_quantity = unit_quantity * resource_quantity
                monthly_amount = unit_monthly_amount * resource_quantity
                description = f"{definition.display_name} — {dimension.label}"
                if resource_quantity != 1:
                    description += f" (x{resource_quantity})"
                line_items.append(CostLineItem(
                    category=definition.category,
                    description=description,
                    sku_id=f"{definition.service_id}-{dimension.dimension_id}",
                    unit=dimension.unit_label,
                    quantity=round(total_quantity, 4),
                    unit_price=round(effective_unit_price, 6),
                    currency=currency,
                    monthly_amount=round(monthly_amount, 2),
                    source=SOURCE_NAME,
                ))

            assumptions.append(Assumption(
                field=f"selected_services.{selection.service_id}",
                requested_value=definition.display_name,
                used_value="priced from indicative public list pricing",
                reason=(
                    f"{definition.display_name} does not yet have a dedicated pricing provider integration; "
                    "its cost is estimated from indicative unit prices, not a live GCP Billing Catalog lookup."
                ),
                strategy_applied="generic_service_catalog",
            ))

        return line_items, assumptions
