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


def test_catalog_machine_family_capabilities_exposes_region_availability():
    """Frontend consumes this endpoint to show the custom-support/region
    indicators on the Sizing step without waiting on a debounced /validate
    call - `available_regions` must actually be present in the response."""
    resp = client.get("/api/v1/catalog/machine-family-capabilities")
    assert resp.status_code == 200
    data = resp.json()
    by_family = {c["family"]: c for c in data}
    assert "available_regions" in by_family["n4a"]
    assert by_family["n4a"]["available_regions"] == ["us-central1", "europe-west4"]
    assert by_family["n2"]["available_regions"] is None


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


def test_estimate_endpoint_predefined_machine_type_by_name():
    payload = {
        "project_name": "N4 Standard Test",
        "region": "us-central1",
        "compute": {"machine_family": "n4", "machine_type": "n4-standard-4", "instance_count": 1},
    }
    resp = client.post("/api/v1/estimate", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["normalized_spec"]["machine_type"] == "n4-standard-4"
    assert body["normalized_spec"]["vcpu"] == 4 and body["normalized_spec"]["ram_gb"] == 16
    assert body["normalized_spec"]["machine_type_kind"] == "predefined"


def test_estimate_endpoint_custom_n2d_configuration():
    payload = {
        "project_name": "Custom N2D API Test",
        "region": "asia-south1",
        "compute": {"machine_family": "n2d", "machine_type_kind": "custom", "vcpu": 2, "ram_gb": 4},
    }
    resp = client.post("/api/v1/estimate", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["normalized_spec"]["machine_type_kind"] == "custom"
    assert body["normalized_spec"]["vcpu"] == 2 and body["normalized_spec"]["ram_gb"] == 4
    compute_line = next(li for li in body["cost"]["line_items"] if li["category"] == "Compute")
    assert "custom" in compute_line["description"].lower()


def test_estimate_endpoint_blocks_unsupported_custom_family_without_force():
    # T2D does not support custom machine types on real Google Cloud.
    payload = {
        "project_name": "Unsupported Custom Family",
        "region": "us-central1",
        "compute": {"machine_family": "t2d", "machine_type_kind": "custom", "vcpu": 4, "ram_gb": 16},
    }
    resp = client.post("/api/v1/estimate", json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_failed"


def test_estimate_endpoint_rejects_missing_machine_type_and_sizing():
    payload = {
        "project_name": "Neither Machine Type Nor Sizing",
        "region": "us-central1",
        "compute": {"machine_family": "e2"},
    }
    resp = client.post("/api/v1/estimate", json=payload)
    assert resp.status_code == 422  # Pydantic model validation, not the ValidationFailedError path


def test_estimate_endpoint_normalizes_machine_family_separator_variant():
    payload = {
        "project_name": "Family Separator Variant",
        "region": "us-central1",
        "compute": {"machine_family": "N2-D", "vcpu": 4, "ram_gb": 16},
    }
    resp = client.post("/api/v1/estimate", json=payload)
    assert resp.status_code == 200
    assert resp.json()["normalized_spec"]["family"] == "n2d"


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


def test_estimate_endpoint_region_query_param_overrides_requirement_region():
    # The backend is the final authority on region (app/domain/region_resolution.py):
    # an explicit `region` query param always wins over whatever the submitted
    # requirement.region already says.
    payload = {
        "project_name": "Region Override Test",
        "region": "us-central1",
        "compute": {"machine_family": "e2", "vcpu": 2, "ram_gb": 8},
    }
    resp = client.post("/api/v1/estimate", json=payload, params={"region": "asia-south1"})
    assert resp.status_code == 200
    assert resp.json()["normalized_spec"]["region"] == "asia-south1"


def test_estimate_endpoint_uses_requirement_region_when_no_override_given():
    payload = {
        "project_name": "No Override Test",
        "region": "europe-west1",
        "compute": {"machine_family": "e2", "vcpu": 2, "ram_gb": 8},
    }
    resp = client.post("/api/v1/estimate", json=payload)
    assert resp.status_code == 200
    assert resp.json()["normalized_spec"]["region"] == "europe-west1"


def test_estimate_endpoint_rejects_invalid_region_override_clearly():
    payload = {
        "project_name": "Bad Override Test",
        "region": "us-central1",
        "compute": {"machine_family": "e2", "vcpu": 2, "ram_gb": 8},
    }
    resp = client.post("/api/v1/estimate", json=payload, params={"region": "not-a-real-region"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_region"


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
