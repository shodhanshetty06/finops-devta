"""Generic GCP service catalog models - the data-driven alternative to a
one-off Pydantic model per resource type (see catalog/models.py). A
GCPServiceDefinition is enough metadata for the frontend to render a search-
able, categorized service picker and a fully dynamic configuration form
(configuration_schema) without any per-service branching, and enough for the
backend to generically validate (ServiceCatalogConfigValidationRule) and
price (GenericServicePricingCalculator) any service that has no dedicated
typed model."""
from typing import Any, Literal

from pydantic import BaseModel, Field

LegacyBinding = Literal["storage", "database", "kubernetes"]
ConfigFieldType = Literal["number", "select", "boolean", "text"]


class ConfigFieldOption(BaseModel):
    value: str
    label: str


class ConfigFieldSchema(BaseModel):
    """One input in a service's dynamic configuration form. `field_id` is
    also the key used in `ServiceSelection.config`.

    `group` is an optional section label (e.g. "Scaling Constraints") the
    frontend uses to render related fields together under a subheading
    instead of one flat list - purely cosmetic, never read by pricing."""

    field_id: str
    label: str
    field_type: ConfigFieldType
    unit: str | None = None
    default: Any = None
    min_value: float | None = None
    max_value: float | None = None
    options: list[ConfigFieldOption] | None = None
    required: bool = True
    help_text: str | None = None
    group: str | None = None


class PricingDimension(BaseModel):
    """One line item the generic pricing calculator will produce for a
    service: `quantity = config[config_field_id] / quantity_divisor`,
    `monthly_amount = quantity * effective_unit_price`.

    `effective_unit_price` is normally just `unit_price_usd`, but when
    `rate_selector_field_id` is set, the calculator instead looks up
    `config[rate_selector_field_id]` in `rate_by_option` (falling back to
    `unit_price_usd` if the selected option isn't in the map) - this is how
    a dimension's price varies by another field's selected value (e.g.
    Cloud Storage's $/GB varying by `storage_class`, or Cloud SQL's hourly
    rate varying by `high_availability`) without a per-service branch in the
    pricing calculator itself."""

    dimension_id: str
    label: str
    config_field_id: str
    unit_label: str
    unit_price_usd: float
    quantity_divisor: float = 1.0
    rate_selector_field_id: str | None = None
    rate_by_option: dict[str, float] | None = None


class GCPServiceDefinition(BaseModel):
    """A single entry in the GCP service catalog. Conceptually:
    service_id / display_name / category / description / configuration_schema
    / pricing_dimensions / active - exactly the model requested for a
    scalable, non-hardcoded service catalog."""

    service_id: str
    display_name: str
    category: str
    description: str
    icon: str = "box"  # lucide-react icon name, rendered generically on the frontend
    configuration_schema: list[ConfigFieldSchema] = Field(default_factory=list)
    pricing_dimensions: list[PricingDimension] = Field(default_factory=list)
    legacy_binding: LegacyBinding | None = None
    active: bool = True
