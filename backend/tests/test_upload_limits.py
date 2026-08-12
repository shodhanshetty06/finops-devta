"""Tests for the Phase 10 security review fix: Excel questionnaire uploads
used to call `await file.read()` with no size limit, which was an
*unauthenticated* memory-exhaustion vector on POST /api/v1/intake/excel (it
has no auth requirement at all). Uses a monkeypatched low limit rather than
a real 10 MB+ upload so the test stays fast."""
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from tests.conftest import register_and_login


@pytest.fixture
def small_limit_client(db_session, monkeypatch):
    monkeypatch.setenv("FINOPS_MAX_UPLOAD_SIZE_BYTES", "1024")  # 1 KB
    get_settings.cache_clear()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_stateless_intake_rejects_oversized_upload(small_limit_client):
    oversized = b"x" * (2 * 1024)  # 2 KB, over the 1 KB test limit
    resp = small_limit_client.post(
        "/api/v1/intake/excel",
        files={"file": ("big.xlsx", oversized, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 413
    assert resp.json()["error"] == "payload_too_large"


def test_stateless_intake_accepts_upload_within_limit(small_limit_client):
    small = b"x" * 512  # under the 1 KB test limit (not a valid workbook, but should get past the size check)
    resp = small_limit_client.post(
        "/api/v1/intake/excel",
        files={"file": ("small.xlsx", small, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code != 413


def test_project_intake_rejects_oversized_upload(small_limit_client):
    _, headers = register_and_login(small_limit_client, "upload-limit@example.com")
    project = small_limit_client.post("/api/v1/projects", json={"name": "Upload Limit Project"}, headers=headers).json()

    oversized = b"x" * (2 * 1024)
    resp = small_limit_client.post(
        f"/api/v1/projects/{project['id']}/intake/excel",
        files={"file": ("big.xlsx", oversized, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 413
    assert resp.json()["error"] == "payload_too_large"
