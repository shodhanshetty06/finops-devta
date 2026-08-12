from tests.conftest import register_and_login

COMPUTE_REQUIREMENT = {
    "project_name": "Optimization Target",
    "region": "us-central1",
    "normalization_strategy": "balanced",
    "compute": {"machine_family": "e2", "vcpu": 8, "ram_gb": 32, "instance_count": 1},
    "storage": {"disk_type": "pd-balanced", "size_gb": 100},
}


def test_optimization_endpoints_require_authentication(api_client):
    resp = api_client.post("/api/v1/optimization/forecast", json={
        "requirement": COMPUTE_REQUIREMENT, "monthly_growth_percent": 5, "months": 3,
    })
    assert resp.status_code == 401


def test_rightsizing_endpoint(api_client):
    _, headers = register_and_login(api_client, "opt-rightsizing@example.com")
    resp = api_client.post(
        "/api/v1/optimization/rightsizing",
        json={
            "requirement": COMPUTE_REQUIREMENT,
            "usage": {"avg_cpu_utilization_percent": 10, "peak_cpu_utilization_percent": 15, "observation_period_days": 30},
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["findings"][0]["action"] == "downsize"
    assert body["total_monthly_savings"] > 0


def test_commitment_recommendation_endpoint(api_client):
    _, headers = register_and_login(api_client, "opt-commitment@example.com")
    resp = api_client.post(
        "/api/v1/optimization/commitment-recommendation",
        json={"requirement": COMPUTE_REQUIREMENT, "workload_stability": "steady"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["options"]) == 2
    assert body["on_demand_discountable_monthly_cost"] > 0


def test_forecast_endpoint(api_client):
    _, headers = register_and_login(api_client, "opt-forecast@example.com")
    resp = api_client.post(
        "/api/v1/optimization/forecast",
        json={"requirement": COMPUTE_REQUIREMENT, "monthly_growth_percent": 5, "months": 6},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["points"]) == 6
    assert body["points"][0]["projected_monthly_cost"] == body["starting_monthly_cost"]


def test_carbon_endpoint(api_client):
    _, headers = register_and_login(api_client, "opt-carbon@example.com")
    resp = api_client.post(
        "/api/v1/optimization/carbon", json={"requirement": COMPUTE_REQUIREMENT}, headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["estimated_kgco2e_per_month"] > 0
    assert body["region"] == "us-central1"


def test_compare_regions_endpoint(api_client):
    _, headers = register_and_login(api_client, "opt-regions@example.com")
    resp = api_client.post(
        "/api/v1/optimization/compare-regions",
        json={"requirement": COMPUTE_REQUIREMENT, "regions": ["us-central1", "us-west1", "asia-south1"]},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["options"]) == 3
    assert body["cheapest_region"] in {"us-central1", "us-west1", "asia-south1"}


def test_compare_regions_rejects_unknown_region(api_client):
    _, headers = register_and_login(api_client, "opt-regions-bad@example.com")
    resp = api_client.post(
        "/api/v1/optimization/compare-regions",
        json={"requirement": COMPUTE_REQUIREMENT, "regions": ["mars-north1"]},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "unsupported_region"


def test_compare_scenarios_endpoint(api_client):
    _, headers = register_and_login(api_client, "opt-scenarios@example.com")
    resp = api_client.post(
        "/api/v1/optimization/compare-scenarios",
        json={
            "base": COMPUTE_REQUIREMENT,
            "scenarios": [
                {"name": "smaller", "overrides": {"compute": {"vcpu": 2, "ram_gb": 8}}},
                {"name": "eu-region", "overrides": {"region": "europe-west1"}},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["base"]["delta_vs_base_monthly"] == 0
    names = {s["name"] for s in body["scenarios"]}
    assert names == {"smaller", "eu-region"}
    smaller = next(s for s in body["scenarios"] if s["name"] == "smaller")
    assert smaller["total_monthly"] < body["base"]["total_monthly"]
