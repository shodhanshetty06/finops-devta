"""API-level tests for Phase 4 intake endpoints - both the stateless
/api/v1/intake/* endpoints and the project-scoped persistence shortcuts."""
import io

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.intake.excel_template import ExcelTemplateGenerator
from app.main import app
from tests.conftest import register_and_login

client = TestClient(app)


def _filled_questionnaire_bytes(values: dict[str, object]) -> bytes:
    blank = ExcelTemplateGenerator().generate()
    wb = load_workbook(io.BytesIO(blank))
    ws = wb["Questionnaire"]
    for row in ws.iter_rows():
        label = row[0].value
        if label in values:
            row[1].value = values[label]
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


GOOD_QUESTIONNAIRE = {
    "Project Name": "API Excel Test",
    "Region": "us-central1",
    "Machine Family": "e2",
    "vCPU": 4,
    "RAM (GB)": 16,
    "Instance Count": 1,
}


def test_download_template_endpoint():
    resp = client.get("/api/v1/intake/excel/template")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert resp.content[:2] == b"PK"


def test_upload_excel_returns_parsed_requirement():
    file_bytes = _filled_questionnaire_bytes(GOOD_QUESTIONNAIRE)
    resp = client.post(
        "/api/v1/intake/excel",
        files={"file": ("questionnaire.xlsx", file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["requirement"]["project_name"] == "API Excel Test"
    assert body["issues"] == []
    assert body["estimate"] is None


def test_upload_excel_with_auto_estimate_returns_priced_result():
    file_bytes = _filled_questionnaire_bytes(GOOD_QUESTIONNAIRE)
    resp = client.post(
        "/api/v1/intake/excel?auto_estimate=true",
        files={"file": ("questionnaire.xlsx", file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["estimate"] is not None
    assert body["estimate"]["cost"]["total_monthly"] > 0


def test_upload_unreadable_file_returns_400():
    resp = client.post(
        "/api/v1/intake/excel",
        files={"file": ("bad.xlsx", b"not a real workbook", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "intake_parse_error"


def test_text_extraction_endpoint():
    resp = client.post("/api/v1/intake/text", json={
        "project_name": "Text Test",
        "text": "500 users, HA required, 99.99% uptime, 100GB database.",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["requirement"]["business"]["total_users"] == 500
    assert body["requirement"]["availability"]["high_availability"] is True
    assert len(body["notes"]) > 0


def test_text_extraction_with_auto_estimate():
    resp = client.post("/api/v1/intake/text?auto_estimate=true", json={
        "project_name": "Text Test Priced",
        "text": "500 users, HA required, 99.99% uptime, 100GB database.",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["estimate"] is not None
    assert body["estimate"]["cost"]["total_monthly"] > 0
    # This request had no compute section, so the AI recommendation engine
    # should have filled it in - confirm that shows up as an assumption.
    assert any(a["strategy_applied"] == "ai_recommendation" for a in body["estimate"]["assumptions"])


def test_project_intake_excel_creates_version(api_client):
    _, headers = register_and_login(api_client, "intake-excel@example.com")
    project = api_client.post("/api/v1/projects", json={"name": "Intake Excel Project"}, headers=headers).json()

    file_bytes = _filled_questionnaire_bytes(GOOD_QUESTIONNAIRE)
    resp = api_client.post(
        f"/api/v1/projects/{project['id']}/intake/excel",
        files={"file": ("q.xlsx", file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["version"] == 1
    assert body["result"]["cost"]["total_monthly"] > 0


def test_project_intake_excel_unparseable_returns_400(api_client):
    _, headers = register_and_login(api_client, "intake-bad@example.com")
    project = api_client.post("/api/v1/projects", json={"name": "Bad Intake Project"}, headers=headers).json()

    blank = ExcelTemplateGenerator().generate()  # no project name filled in -> unparseable
    resp = api_client.post(
        f"/api/v1/projects/{project['id']}/intake/excel",
        files={"file": ("blank.xlsx", blank, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "intake_parse_error"

    # Confirm nothing was persisted.
    resp = api_client.get(f"/api/v1/projects/{project['id']}/estimates", headers=headers)
    assert resp.json() == []


def test_project_intake_text_creates_version(api_client):
    _, headers = register_and_login(api_client, "intake-text@example.com")
    project = api_client.post("/api/v1/projects", json={"name": "Intake Text Project"}, headers=headers).json()

    resp = api_client.post(
        f"/api/v1/projects/{project['id']}/intake/text",
        json={"project_name": "From Text", "text": "500 users, HA required, 99.99% uptime, 100GB database."},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["version"] == 1
    assert body["request"]["project_name"] == "From Text"
    assert body["result"]["cost"]["total_monthly"] > 0


def test_project_intake_requires_authentication(api_client):
    resp = api_client.post(
        "/api/v1/projects/1/intake/text",
        json={"project_name": "x", "text": "500 users"},
    )
    assert resp.status_code == 401
