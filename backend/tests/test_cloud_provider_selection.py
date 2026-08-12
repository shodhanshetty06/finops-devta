"""Tests for FINOPS_CLOUD_PROVIDER dependency-injection wiring (Phase 9) and
a regression test for the Phase 5-era bug it fixes: catalog provider
resolution used to be gated on FINOPS_PRICING_PROVIDER=="gcp" and raised
NotImplementedError in that case, which meant enabling live GCP pricing
broke the app entirely at catalog-resolution time. Settings/provider caches
are always cleared before and after each test so this module never leaks
state into the rest of the suite (same pattern as test_rate_limit.py)."""
import pytest
from fastapi.testclient import TestClient

from app.catalog.aws_provider import AwsCatalogProvider
from app.catalog.azure_provider import AzureCatalogProvider
from app.catalog.dependency import get_catalog_provider
from app.catalog.mock_provider import MockCatalogProvider
from app.core.config import Settings, get_settings
from app.main import app
from app.pricing.aws_provider import AwsPricingProvider
from app.pricing.azure_provider import AzurePricingProvider
from app.pricing.dependency import get_pricing_provider
from app.pricing.mock_provider import MockGCPPricingProvider


def _clear_caches():
    get_settings.cache_clear()
    get_catalog_provider.cache_clear()
    get_pricing_provider.cache_clear()


@pytest.fixture(autouse=True)
def _isolate_caches():
    _clear_caches()
    yield
    _clear_caches()


def test_cloud_provider_defaults_to_gcp():
    assert Settings().cloud_provider == "gcp"


def test_cloud_provider_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("FINOPS_CLOUD_PROVIDER", "digitalocean")
    with pytest.raises(ValueError):
        Settings()


def test_gcp_cloud_provider_resolves_mock_providers_by_default(monkeypatch):
    monkeypatch.setenv("FINOPS_CLOUD_PROVIDER", "gcp")
    _clear_caches()
    assert isinstance(get_catalog_provider(), MockCatalogProvider)
    assert isinstance(get_pricing_provider(), MockGCPPricingProvider)


def test_gcp_pricing_provider_gcp_no_longer_breaks_catalog_resolution(monkeypatch):
    """Regression test: this used to raise NotImplementedError."""
    monkeypatch.setenv("FINOPS_CLOUD_PROVIDER", "gcp")
    monkeypatch.setenv("FINOPS_PRICING_PROVIDER", "gcp")
    monkeypatch.setenv("FINOPS_GCP_API_KEY", "fake-key-for-construction-only")
    _clear_caches()
    # Catalog resolution must succeed regardless of the live/mock pricing toggle.
    assert isinstance(get_catalog_provider(), MockCatalogProvider)


def test_aws_cloud_provider_resolves_aws_providers(monkeypatch):
    monkeypatch.setenv("FINOPS_CLOUD_PROVIDER", "aws")
    _clear_caches()
    assert isinstance(get_catalog_provider(), AwsCatalogProvider)
    assert isinstance(get_pricing_provider(), AwsPricingProvider)


def test_azure_cloud_provider_resolves_azure_providers(monkeypatch):
    monkeypatch.setenv("FINOPS_CLOUD_PROVIDER", "azure")
    _clear_caches()
    assert isinstance(get_catalog_provider(), AzureCatalogProvider)
    assert isinstance(get_pricing_provider(), AzurePricingProvider)


COMPUTE_REQUIREMENT = {
    "project_name": "Cross-cloud smoke test",
    "region": "us-central1",
    "normalization_strategy": "balanced",
    "compute": {"machine_family": "n2", "vcpu": 4, "ram_gb": 16, "instance_count": 1},
    "storage": {"disk_type": "pd-balanced", "size_gb": 100},
}


def test_estimate_endpoint_runs_end_to_end_under_aws(monkeypatch):
    monkeypatch.setenv("FINOPS_CLOUD_PROVIDER", "aws")
    _clear_caches()
    client = TestClient(app)
    resp = client.post("/api/v1/estimate", json=COMPUTE_REQUIREMENT)
    assert resp.status_code == 200
    body = resp.json()
    assert body["normalized_spec"]["machine_type"].startswith("m5.")
    assert body["cost"]["line_items"][0]["source"] == "aws_mock_catalog"
    assert body["cost"]["total_monthly"] > 0


def test_estimate_endpoint_runs_end_to_end_under_azure(monkeypatch):
    monkeypatch.setenv("FINOPS_CLOUD_PROVIDER", "azure")
    _clear_caches()
    client = TestClient(app)
    resp = client.post("/api/v1/estimate", json=COMPUTE_REQUIREMENT)
    assert resp.status_code == 200
    body = resp.json()
    assert body["normalized_spec"]["machine_type"].startswith("Standard_D")
    assert body["cost"]["line_items"][0]["source"] == "azure_mock_catalog"
    assert body["cost"]["total_monthly"] > 0


def test_estimate_endpoint_still_works_under_gcp_default():
    client = TestClient(app)
    resp = client.post("/api/v1/estimate", json=COMPUTE_REQUIREMENT)
    assert resp.status_code == 200
    body = resp.json()
    assert body["normalized_spec"]["machine_type"].startswith("n2-standard")
    assert body["cost"]["line_items"][0]["source"] == "mock_catalog"
