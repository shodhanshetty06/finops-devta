from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_catalog_machine_types():
    resp = client.get("/api/v1/catalog/machine-types", params={"family": "e2"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert all(m["family"] == "e2" for m in data)


def test_validate_endpoint():
    payload = {
        "project_name": "API Test",
        "region": "us-central1",
        "compute": {"machine_family": "e2", "vcpu": 3, "ram_gb": 10},
    }
    resp = client.post("/api/v1/validate", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert any(r["rule"] == "cpu_validation" and r["is_valid"] is False for r in body["results"])


def test_estimate_endpoint_full_pipeline():
    payload = {
        "project_name": "API Estimate Test",
        "region": "us-central1",
        "compute": {"machine_family": "e2", "vcpu": 4, "ram_gb": 16, "instance_count": 2},
        "storage": {"disk_type": "pd-balanced", "size_gb": 100},
        "network": {"load_balancer_required": True, "external_ip_count": 1},
    }
    resp = client.post("/api/v1/estimate", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["cost"]["total_monthly"] > 0
    assert body["cost"]["total_yearly"] == round(body["cost"]["total_monthly"] * 12, 2)
    assert "audit_log" in body
    assert len(body["audit_log"]["entries"]) > 0


def test_estimate_endpoint_blocks_on_blocker_without_force():
    payload = {
        "project_name": "Bad GPU",
        "region": "us-central1",
        "compute": {"machine_family": "e2", "vcpu": 4, "ram_gb": 16,
                     "gpu_type": "nvidia-tesla-a100", "gpu_count": 1},
    }
    resp = client.post("/api/v1/estimate", json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_failed"


def test_estimate_endpoint_business_only():
    payload = {
        "project_name": "Business Only API Test",
        "region": "us-central1",
        "business": {"total_users": 500, "peak_concurrent_users": 500},
        "availability": {"high_availability": True, "target_uptime_percent": 99.99},
    }
    resp = client.post("/api/v1/estimate", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["assumptions"]) > 0
    assert body["cost"]["total_monthly"] > 0


def test_openapi_docs_available():
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"]


def _get_sample_estimate_json():
    payload = {
        "project_name": "Report Export Test",
        "region": "us-central1",
        "compute": {"machine_family": "e2", "vcpu": 4, "ram_gb": 16, "instance_count": 2},
        "storage": {"disk_type": "pd-balanced", "size_gb": 100},
        "network": {"load_balancer_required": True, "external_ip_count": 1},
    }
    resp = client.post("/api/v1/estimate", json=payload)
    assert resp.status_code == 200
    return resp.json()


def test_reports_excel_endpoint_returns_downloadable_workbook():
    estimate = _get_sample_estimate_json()
    resp = client.post("/api/v1/reports/excel", json={"estimate": estimate, "branding": {"prepared_for": "Acme Co."}})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.content[:2] == b"PK"  # xlsx is a zip archive


def test_reports_pdf_endpoint_returns_downloadable_pdf():
    estimate = _get_sample_estimate_json()
    resp = client.post("/api/v1/reports/pdf", json={"estimate": estimate})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.content[:5] == b"%PDF-"
