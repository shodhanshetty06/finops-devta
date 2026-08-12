"""API-level tests for the Phase 7 async job endpoints. The suite runs with
FINOPS_CELERY_TASK_ALWAYS_EAGER=true (see conftest.py), so a job is already
finished by the time `.delay()` returns - these tests exercise the full
enqueue -> poll -> download contract even though nothing is actually
queued in-process during the test run."""
import base64

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _sample_estimate_json(client_: TestClient) -> dict:
    resp = client_.post("/api/v1/estimate", json={
        "project_name": "Jobs API Test",
        "region": "us-central1",
        "compute": {"machine_family": "e2", "vcpu": 2, "ram_gb": 8, "instance_count": 1},
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_enqueue_report_job_returns_202_and_job_id():
    estimate = _sample_estimate_json(client)
    resp = client.post("/api/v1/jobs/reports", json={"estimate": estimate, "format": "excel"})
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["job_id"]


def test_report_job_status_then_download_excel():
    estimate = _sample_estimate_json(client)
    job_id = client.post("/api/v1/jobs/reports", json={"estimate": estimate, "format": "excel"}).json()["job_id"]

    status_resp = client.get(f"/api/v1/jobs/{job_id}")
    assert status_resp.status_code == 200
    status = status_resp.json()
    assert status["state"] == "SUCCESS"
    assert status["ready"] is True
    assert status["successful"] is True
    assert status["result"]["filename"].endswith(".xlsx")
    assert "data_b64" not in status["result"]  # status responses omit the payload

    download_resp = client.get(f"/api/v1/jobs/{job_id}/download")
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert download_resp.content[:2] == b"PK"


def test_report_job_pdf_download():
    estimate = _sample_estimate_json(client)
    job_id = client.post("/api/v1/jobs/reports", json={"estimate": estimate, "format": "pdf"}).json()["job_id"]
    download_resp = client.get(f"/api/v1/jobs/{job_id}/download")
    assert download_resp.status_code == 200
    assert download_resp.content[:5] == b"%PDF-"


def test_download_endpoint_rejects_non_report_job():
    resp = client.post("/api/v1/jobs/batch-estimate", json={
        "items": [{"project_name": "X", "region": "us-central1", "compute": {"machine_family": "e2", "vcpu": 2, "ram_gb": 8}}],
    })
    job_id = resp.json()["job_id"]
    download_resp = client.get(f"/api/v1/jobs/{job_id}/download")
    assert download_resp.status_code == 400


def test_download_unknown_job_id_returns_425_not_ready():
    resp = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000/download")
    # An unknown id looks PENDING to Celery (it never ran), which this
    # endpoint correctly treats as "not finished yet", not "not found" -
    # Celery has no concept of a job id that was never issued.
    assert resp.status_code == 425


def test_enqueue_batch_estimate_job_and_poll_result():
    resp = client.post("/api/v1/jobs/batch-estimate", json={
        "items": [
            {"project_name": "Batch A", "region": "us-central1", "compute": {"machine_family": "e2", "vcpu": 2, "ram_gb": 8}},
            {"project_name": "Batch B", "region": "us-central1", "compute": {"machine_family": "n2", "vcpu": 4, "ram_gb": 16}},
        ],
    })
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    status = client.get(f"/api/v1/jobs/{job_id}").json()
    assert status["successful"] is True
    assert status["result"]["total"] == 2
    assert status["result"]["succeeded"] == 2
    assert len(status["result"]["items"]) == 2


def test_batch_estimate_job_requires_at_least_one_item():
    resp = client.post("/api/v1/jobs/batch-estimate", json={"items": []})
    assert resp.status_code == 422


def test_report_job_invalid_format_rejected_by_schema():
    estimate = _sample_estimate_json(client)
    resp = client.post("/api/v1/jobs/reports", json={"estimate": estimate, "format": "csv"})
    assert resp.status_code == 422  # format is a Literal["excel", "pdf"]
