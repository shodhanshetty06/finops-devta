"""Cost / pricing domain models. The AI layer never populates the numeric
`unit_price` or `amount` fields itself - those always originate from a
PricingProvider (mock today, live Google Cloud Billing Catalog API later)."""
from pydantic import BaseModel, Field


class CostLineItem(BaseModel):
    category: str            # e.g. "Compute", "Storage", "Database", "Network", "GPU", "Support", "Tax"
    description: str         # e.g. "e2-standard-4 x 2 instances (us-central1)"
    sku_id: str | None = None
    unit: str                # e.g. "hour", "GB-month", "request"
    quantity: float
    unit_price: float
    currency: str
    monthly_amount: float
    source: str               # e.g. "gcp_billing_catalog_api" or "mock_catalog"


class DiscountLineItem(BaseModel):
    name: str                 # e.g. "Sustained Use Discount", "1-Year CUD"
    description: str
    percent_off: float
    monthly_savings: float


class ResourceCostSummary(BaseModel):
    """One row per distinct resource/configuration on the estimate -
    GCP-service-catalog selections (app/catalog/resource_summary.py) AND
    legacy typed resources: Compute Engine, Persistent Disk, Cloud SQL,
    Networking, GKE (app/catalog/legacy_resource_summary.py) - resource
    name, its configuration, an explicit quantity, the cost of one unit,
    and quantity x unit_cost. Selections/resources with the same
    pricing-relevant configuration are merged into a single row (their
    quantities summed); different configurations get their own row.

    `unit_cost`/`subtotal` are always derived from CostLineItems the
    pricing pipeline already computed - never recomputed here - so
    sum(subtotal for every row) always reconciles exactly with
    CostBreakdown.subtotal_monthly (see CostBreakdown.category_totals)."""

    resource_name: str
    configuration: str
    quantity: int
    unit_cost: float
    subtotal: float
    currency: str

    # Additive fields - all optional/defaulted so a pre-existing saved
    # estimate (persisted before these existed) still deserializes cleanly.
    category: str | None = None            # e.g. "Compute", "Storage", "Database", "Network"
    sku_id: str | None = None              # None when a row aggregates multiple SKUs
    pricing_source: str | None = None      # e.g. "gcp_billing_catalog_api" or "mock_catalog"
    region: str | None = None
    requested_configuration: str | None = None
    normalized_configuration: str | None = None
    # "valid" | "normalized" | "assumption" | "unsupported"
    status: str = "valid"
    assumption_reason: str | None = None


class CostBreakdown(BaseModel):
    currency: str
    line_items: list[CostLineItem]
    discounts: list[DiscountLineItem]
    # Additive, resource-oriented view of every resource on the estimate
    # (catalog selections AND legacy compute/storage/database/network/GKE
    # resources - see ResourceCostSummary). Never used to compute totals;
    # totals are still derived exclusively from `line_items`, same as
    # before this field existed.
    resource_summaries: list[ResourceCostSummary] = Field(default_factory=list)
    # sum(category_totals.values()) == sum(r.subtotal for r in
    # resource_summaries) == subtotal_monthly (pre-discount/tax/support;
    # total_monthly applies those on top of this, same as it always has).
    category_totals: dict[str, float] = Field(default_factory=dict)

    subtotal_monthly: float
    discount_total_monthly: float
    tax_rate_percent: float
    tax_monthly: float
    support_plan_percent: float
    support_monthly: float

    total_monthly: float
    total_yearly: float
    total_three_year: float
