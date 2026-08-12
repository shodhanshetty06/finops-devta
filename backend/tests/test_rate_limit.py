"""Tests for the rate limit middleware. Rate limiting is disabled for the
rest of the suite (see conftest.py) to avoid the normal test run's request
volume tripping it - these tests explicitly re-enable it with a low limit
via a dedicated fixture, and always leave global caches clean afterward so
later test modules keep seeing the suite-wide "disabled" default."""
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.middleware.rate_limit import get_rate_limiter


@pytest.fixture
def rate_limited_client(db_session, monkeypatch):
    monkeypatch.setenv("FINOPS_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("FINOPS_RATE_LIMIT_REQUESTS_PER_MINUTE", "5")
    monkeypatch.setenv("FINOPS_RATE_LIMIT_HEAVY_REQUESTS_PER_MINUTE", "2")
    get_settings.cache_clear()
    get_rate_limiter.cache_clear()

    # Wired to an isolated, table-created DB (same pattern as the api_client
    # fixture in conftest.py) so DB-backed endpoints - e.g. /api/v1/auth/login,
    # added to the heavy rate-limit bucket in Phase 10 - work under this
    # fixture too, not just the stateless endpoints the original tests here used.
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
        get_rate_limiter.cache_clear()


def test_standard_endpoint_allows_up_to_the_limit(rate_limited_client):
    for _ in range(5):
        resp = rate_limited_client.get("/api/v1/catalog/regions")
        assert resp.status_code == 200


def test_standard_endpoint_rejects_beyond_the_limit(rate_limited_client):
    for _ in range(5):
        rate_limited_client.get("/api/v1/catalog/regions")
    resp = rate_limited_client.get("/api/v1/catalog/regions")
    assert resp.status_code == 429
    assert resp.json()["error"] == "rate_limited"
    assert "Retry-After" in resp.headers


def test_heavy_endpoint_has_a_stricter_limit_than_standard(rate_limited_client):
    payload = {"project_name": "RL Test", "region": "us-central1", "compute": {"machine_family": "e2", "vcpu": 2, "ram_gb": 8}}
    for _ in range(2):
        resp = rate_limited_client.post("/api/v1/estimate", json=payload)
        assert resp.status_code == 200
    resp = rate_limited_client.post("/api/v1/estimate", json=payload)
    assert resp.status_code == 429


def test_login_endpoint_uses_the_heavy_limit(rate_limited_client):
    """Phase 10 security review: /api/v1/auth/login is throttled at the
    heavy (stricter) limit specifically to slow brute-force/credential-
    stuffing attempts, not because it's CPU-expensive."""
    payload = {"username": "nobody@example.com", "password": "wrong-password"}
    for _ in range(2):
        resp = rate_limited_client.post("/api/v1/auth/login", data=payload)
        assert resp.status_code == 401  # wrong credentials, but not yet rate-limited
    resp = rate_limited_client.post("/api/v1/auth/login", data=payload)
    assert resp.status_code == 429


def test_health_endpoint_is_exempt_from_rate_limiting(rate_limited_client):
    for _ in range(10):
        resp = rate_limited_client.get("/health")
        assert resp.status_code == 200


def test_rate_limit_counters_are_independent_per_bucket(rate_limited_client):
    # Exhausting the "heavy" bucket shouldn't affect the "standard" bucket.
    payload = {"project_name": "RL Test", "region": "us-central1", "compute": {"machine_family": "e2", "vcpu": 2, "ram_gb": 8}}
    for _ in range(3):
        rate_limited_client.post("/api/v1/estimate", json=payload)  # exhausts heavy (limit 2)
    resp = rate_limited_client.get("/api/v1/catalog/regions")
    assert resp.status_code == 200
