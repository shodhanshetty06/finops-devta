import os
import tempfile

# Must be set before any app.core.config import triggers Settings() to read
# the environment. bcrypt is deliberately CPU-expensive (that's the point of
# a password hash); a full test run makes dozens of register/login calls, so
# a low work factor here keeps the suite fast without weakening the
# production default (12) that real deployments get.
os.environ.setdefault("FINOPS_BCRYPT_ROUNDS", "4")

# Runs Celery tasks synchronously in-process (see app/tasks/celery_app.py) -
# the suite never needs a real Redis broker or a running worker. The result
# backend is likewise swapped for Celery's built-in in-process cache
# backend (no Redis needed) - the jobs API looks results up later by id via
# a fresh AsyncResult(job_id), so eager mode alone isn't enough; something
# has to actually store the result for that lookup to find.
os.environ.setdefault("FINOPS_CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("FINOPS_CELERY_RESULT_BACKEND", "cache+memory://")

# The rate limit middleware would otherwise reject a normal test run's
# volume of requests to the same "heavy" endpoint (e.g. many /api/v1/estimate
# calls across test_estimation_service.py + test_api.py in the same
# process). Rate limiting has its own dedicated, isolated tests
# (test_rate_limit.py) that explicitly re-enable it with a low limit.
os.environ.setdefault("FINOPS_RATE_LIMIT_ENABLED", "false")

# Never let a real GROQ_API_KEY/GROQ_MODEL that happens to be set in the
# developer's local backend/.env (or CI environment) leak into the suite -
# every test that goes through get_settings()/get_llm_provider() (e.g. any
# TestClient(app) hitting /api/v1/explanations/* or /api/v1/assistant/chat)
# must see Groq as unconfigured, exactly like a deployment with no key set,
# so results never depend on whichever machine the suite runs on. Tests that
# specifically want the "Groq configured" path construct their own
# GroqProvider directly against a mocked transport instead (see
# tests/test_explanation_service.py, tests/test_assistant_service.py,
# tests/test_llm_groq_provider.py) - these are plain assignments, not
# setdefault, so they always win over the .env file regardless of what's in it.
os.environ["GROQ_API_KEY"] = ""
os.environ["GROQ_MODEL"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.catalog.mock_provider import MockCatalogProvider
from app.core.config import Settings
from app.db import models  # noqa: F401  (import registers all ORM models on Base.metadata)
from app.db.base import Base
from app.db.session import get_db
from app.domain.enums import CloudSqlEngine, DiskType, MachineFamily, Region
from app.domain.requirements import (
    ComputeRequirement,
    CustomerRequirement,
    DatabaseRequirement,
    NetworkRequirement,
    StorageRequirement,
)
from app.main import app
from app.pricing.mock_provider import MockGCPPricingProvider
from app.services.estimation_service import EstimationService


@pytest.fixture
def catalog():
    return MockCatalogProvider()


@pytest.fixture
def pricing_provider():
    return MockGCPPricingProvider()


@pytest.fixture
def settings():
    return Settings(default_normalization_strategy="balanced", default_tax_rate_percent=0, support_plan_percent=0)


@pytest.fixture
def sample_estimate(catalog, pricing_provider, settings):
    """A fully priced EstimateResult with compute, storage, database, and
    network sections populated - used by report generator tests so they
    exercise every sheet/section rather than a bare-minimum request."""
    service = EstimationService(catalog=catalog, pricing_provider=pricing_provider, settings=settings)
    req = CustomerRequirement(
        project_name="Retail Inventory API",
        region=Region.US_CENTRAL1,
        normalization_strategy="performance",
        compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=3, ram_gb=10, instance_count=2),
        storage=StorageRequirement(disk_type=DiskType.PD_BALANCED, size_gb=157, snapshot_enabled=True, snapshot_retention_days=14),
        database=DatabaseRequirement(required=True, engine=CloudSqlEngine.POSTGRES, size_gb=100, vcpu=2, ram_gb=8, high_availability=True),
        network=NetworkRequirement(load_balancer_required=True, external_ip_count=1, estimated_egress_gb_per_month=500),
    )
    return service.generate_estimate(req)


# -- Phase 3: persistence/auth test infrastructure ---------------------------
# Each test gets its own throwaway SQLite file so tests never see each
# other's data and never touch the developer's real finops.db.

@pytest.fixture
def test_db_engine():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
    os.remove(path)


@pytest.fixture
def db_session(test_db_engine):
    TestingSessionLocal = sessionmaker(bind=test_db_engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def api_client(db_session):
    """A TestClient wired to the isolated per-test database via dependency
    override, so /auth and /projects endpoints can be exercised end to end
    without touching the developer's real database."""

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def register_and_login(api_client, email: str, password: str = "supersecret123", role: str = "customer",
                        full_name: str = "Test User", db_session=None):
    if role == "admin":
        # POST /api/v1/auth/register deliberately rejects role="admin" (see
        # app/services/auth_service.py - a live QA pass found that letting
        # anonymous callers self-elevate to admin was a real privilege-
        # escalation hole, since ProjectService bypasses the ownership check
        # entirely for admins). Tests that need an admin user seed one
        # directly via the repository layer instead, exactly how a real
        # deployment provisions its first admin (a DB-level operation, not
        # a public API call) - requires the db_session fixture.
        assert db_session is not None, "register_and_login(role='admin') requires db_session=<the db_session fixture>"
        from app.core.security import hash_password
        from app.repositories.user_repository import UserRepository

        UserRepository(db_session).create(
            email=email, hashed_password=hash_password(password), full_name=full_name, role=role,
        )
        resp = api_client.post("/api/v1/auth/login", data={"username": email, "password": password})
        assert resp.status_code == 200, resp.text
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        user = api_client.get("/api/v1/auth/me", headers=headers).json()
        return user, headers

    resp = api_client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "full_name": full_name, "role": role,
    })
    assert resp.status_code == 201, resp.text
    user = resp.json()

    resp = api_client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return user, {"Authorization": f"Bearer {token}"}
