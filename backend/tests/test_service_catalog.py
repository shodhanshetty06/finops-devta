from fastapi.testclient import TestClient

from app.catalog.generic_pricing import GenericServicePricingCalculator
from app.catalog.service_catalog_bridge import apply_bridged_services
from app.domain.enums import MachineFamily, Region
from app.domain.requirements import ComputeRequirement, CustomerRequirement, ServiceSelection
from app.main import app
from app.validation.rules import ServiceCatalogConfigValidationRule

client = TestClient(app)


def _requirement(**selected_service_kwargs) -> CustomerRequirement:
    selections = [ServiceSelection(**kwargs) for kwargs in selected_service_kwargs.get("selections", [])]
    return CustomerRequirement(project_name="Catalog test", region=Region.US_CENTRAL1, selected_services=selections)


# -- Bridge adapter -----------------------------------------------------

def test_bridge_maps_persistent_disk_to_storage_requirement():
    req = _requirement(selections=[
        {"service_id": "persistent-disk", "config": {"disk_type": "pd-ssd", "size_gb": 200, "snapshot_enabled": True, "snapshot_retention_days": 10}},
    ])
    bridged, remaining = apply_bridged_services(req)
    assert remaining == []
    assert bridged.storage is not None
    assert bridged.storage.disk_type.value == "pd-ssd"
    assert bridged.storage.size_gb == 200
    assert bridged.storage.snapshot_retention_days == 10


def test_bridge_maps_cloud_sql_and_gke():
    req = _requirement(selections=[
        {"service_id": "cloud-sql", "config": {"engine": "mysql", "size_gb": 80, "vcpu": 4, "ram_gb": 16, "high_availability": True}},
        {"service_id": "gke", "config": {"autopilot": False, "node_count": 5}},
    ])
    bridged, remaining = apply_bridged_services(req)
    assert remaining == []
    assert bridged.database is not None
    assert bridged.database.required is True
    assert bridged.database.engine.value == "mysql"
    assert bridged.database.high_availability is True
    assert bridged.kubernetes is not None
    assert bridged.kubernetes.required is True
    assert bridged.kubernetes.node_count == 5


def test_networking_services_are_priced_generically_not_bridged():
    """Load Balancing/Cloud CDN/VPN/Network egress have no legacy typed model
    binding - they're priced by GenericServicePricingCalculator like every
    other networking card (Cloud NAT, Cloud Armor, Cloud DNS, VPC,
    Interconnect), so the bridge must leave them in `remaining` untouched."""
    req = _requirement(selections=[
        {"service_id": "load-balancing", "config": {"lb_type": "global_https", "forwarding_rules": 2}},
        {"service_id": "cloud-cdn", "config": {"cache_egress_gb_per_month": 100}},
        {"service_id": "vpn", "config": {"tunnels": 3}},
        {"service_id": "network-egress", "config": {"estimated_egress_gb_per_month": 750}},
    ])
    bridged, remaining = apply_bridged_services(req)
    assert {s.service_id for s in remaining} == {"load-balancing", "cloud-cdn", "vpn", "network-egress"}
    assert bridged.network is None


def test_bridge_leaves_generic_services_in_remaining():
    req = _requirement(selections=[
        {"service_id": "pubsub", "config": {"published_data_gb_per_day": 5}},
        {"service_id": "bigquery", "config": {"tb_scanned_per_month": 5}},
    ])
    bridged, remaining = apply_bridged_services(req)
    assert bridged.storage is None
    assert bridged.database is None
    assert {s.service_id for s in remaining} == {"pubsub", "bigquery"}


def test_bridge_does_not_override_already_set_legacy_field():
    from app.domain.requirements import StorageRequirement
    req = CustomerRequirement(
        project_name="already set", region=Region.US_CENTRAL1,
        storage=StorageRequirement(disk_type="pd-ssd", size_gb=999),
        selected_services=[ServiceSelection(service_id="persistent-disk", config={"disk_type": "pd-standard", "size_gb": 1})],
    )
    bridged, remaining = apply_bridged_services(req)
    assert bridged.storage.size_gb == 999  # untouched, not clobbered by the catalog selection
    assert remaining == []  # still bridged (excluded from generic pricing), just not overwritten


def test_no_selected_services_is_a_no_op():
    req = CustomerRequirement(project_name="none", region=Region.US_CENTRAL1)
    bridged, remaining = apply_bridged_services(req)
    assert bridged is req
    assert remaining == []


# -- Generic pricing calculator ------------------------------------------

def test_generic_pricing_calculator_computes_line_items():
    # Pub/Sub itself is no longer priced by the flat generic calculator (see
    # test_messaging_observability_pricing.py) - Eventarc exercises the same
    # flat config_value/divisor*unit_price mechanism for a still-generic service.
    calc = GenericServicePricingCalculator()
    line_items, assumptions = calc.calculate(
        [ServiceSelection(service_id="eventarc", config={"events_per_month": 200_000_000})], "USD",
    )
    assert len(line_items) == 1
    item = line_items[0]
    assert item.category == "Messaging & Eventing"
    assert item.monthly_amount == 2000.0  # (200_000_000 / 1_000_000) * 10.0
    assert item.currency == "USD"
    assert len(assumptions) == 1
    assert assumptions[0].field == "selected_services.eventarc"


def test_generic_pricing_calculator_skips_sku_priced_services():
    # pubsub/cloud-logging are priced by MessagingObservabilityPricingCalculator
    # instead - the generic calculator must not double-price or double-emit
    # assumptions for them.
    calc = GenericServicePricingCalculator()
    line_items, assumptions = calc.calculate(
        [ServiceSelection(service_id="pubsub", config={"published_data_gb_per_day": 1}),
         ServiceSelection(service_id="cloud-logging", config={"log_volume_gb_per_month": 30})],
        "USD",
    )
    assert line_items == []
    assert assumptions == []


def test_generic_pricing_uses_field_default_when_config_omitted():
    calc = GenericServicePricingCalculator()
    line_items, _ = calc.calculate([ServiceSelection(service_id="spanner", config={})], "USD")
    # processing_units default=100 (its min_value), unit_price 65.0/100 units -> 65.0
    compute_line = next(li for li in line_items if li.sku_id == "spanner-compute")
    assert compute_line.monthly_amount == 65.0


def test_generic_pricing_skips_unknown_service_id():
    calc = GenericServicePricingCalculator()
    line_items, assumptions = calc.calculate([ServiceSelection(service_id="not-a-real-service", config={})], "USD")
    assert line_items == []
    assert len(assumptions) == 1
    assert "not-a-real-service" in assumptions[0].requested_value


def test_generic_pricing_no_op_on_empty_list():
    calc = GenericServicePricingCalculator()
    line_items, assumptions = calc.calculate([], "USD")
    assert line_items == [] and assumptions == []


# -- Generic validation rule ---------------------------------------------

def test_validation_rule_flags_missing_required_field(catalog, monkeypatch):
    # Every field in the real catalog ships with a sensible default (so the
    # dynamic form is always pre-filled), so "required and truly missing"
    # can't be reached with real catalog data - exercise the rule's logic
    # directly against a synthetic definition with no default instead.
    from app.catalog.service_catalog import ConfigFieldSchema, GCPServiceDefinition
    import app.validation.rules as rules_module

    fake_definition = GCPServiceDefinition(
        service_id="fake-service", display_name="Fake Service", category="Test",
        description="", configuration_schema=[
            ConfigFieldSchema(field_id="quota", label="Quota", field_type="number", required=True, default=None),
        ],
    )
    monkeypatch.setitem(rules_module.SERVICE_CATALOG_BY_ID, "fake-service", fake_definition)

    rule = ServiceCatalogConfigValidationRule()
    req = _requirement(selections=[{"service_id": "fake-service", "config": {}}])
    results = rule.evaluate(req, catalog)
    assert len(results) == 1
    assert results[0].severity.value == "warning"
    assert "Quota" in results[0].reason


def test_validation_rule_flags_out_of_range_value(catalog):
    rule = ServiceCatalogConfigValidationRule()
    req = _requirement(selections=[{"service_id": "pubsub", "config": {"topic_retention_days": 100}}])
    results = rule.evaluate(req, catalog)
    assert len(results) == 1
    assert results[0].is_valid is False
    assert "retention" in results[0].reason.lower()


def test_validation_rule_flags_invalid_select_option(catalog):
    rule = ServiceCatalogConfigValidationRule()
    req = _requirement(selections=[{"service_id": "cloud-sql", "config": {"engine": "oracle", "size_gb": 10, "vcpu": 2, "ram_gb": 8}}])
    results = rule.evaluate(req, catalog)
    assert len(results) == 1
    assert results[0].is_valid is False


def test_validation_rule_flags_unknown_service(catalog):
    rule = ServiceCatalogConfigValidationRule()
    req = _requirement(selections=[{"service_id": "nonexistent", "config": {}}])
    results = rule.evaluate(req, catalog)
    assert len(results) == 1
    assert results[0].severity.value == "warning"


def test_validation_rule_passes_valid_selection(catalog):
    rule = ServiceCatalogConfigValidationRule()
    req = _requirement(selections=[{"service_id": "pubsub", "config": {"published_data_gb_per_day": 1}}])
    results = rule.evaluate(req, catalog)
    assert len(results) == 1
    assert results[0].is_valid is True


def test_validation_rule_never_blocks(catalog):
    # A malformed catalog selection should never be a BLOCKER - it must not
    # regress the existing "block on blocker unless force=True" pipeline
    # behavior for requests that also carry a valid legacy section.
    rule = ServiceCatalogConfigValidationRule()
    req = _requirement(selections=[{"service_id": "nonexistent", "config": {}}])
    results = rule.evaluate(req, catalog)
    assert all(r.severity.value != "blocker" for r in results)


# -- API endpoint ----------------------------------------------------------

def test_list_services_endpoint_returns_full_catalog():
    resp = client.get("/api/v1/catalog/services")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 40
    assert any(s["service_id"] == "pubsub" for s in body)


def test_list_services_endpoint_filters_by_category():
    resp = client.get("/api/v1/catalog/services", params={"category": "Database"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 0
    assert all(s["category"] == "Database" for s in body)


def test_list_services_endpoint_filters_by_search():
    resp = client.get("/api/v1/catalog/services", params={"search": "pub/sub"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["service_id"] == "pubsub"


def test_list_service_categories_endpoint():
    resp = client.get("/api/v1/catalog/services/categories")
    assert resp.status_code == 200
    assert "Compute" in resp.json()
