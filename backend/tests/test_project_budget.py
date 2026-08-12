from tests.conftest import register_and_login

COMPUTE_REQUIREMENT = {
    "project_name": "Budget Target",
    "region": "us-central1",
    "normalization_strategy": "balanced",
    "compute": {"machine_family": "e2", "vcpu": 8, "ram_gb": 32, "instance_count": 1},
    "storage": {"disk_type": "pd-balanced", "size_gb": 100},
}


def test_project_has_no_budget_by_default(api_client):
    _, headers = register_and_login(api_client, "budget-default@example.com")
    project = api_client.post("/api/v1/projects", json={"name": "No Budget"}, headers=headers).json()
    assert project["monthly_budget_usd"] is None


def test_set_and_clear_project_budget(api_client):
    _, headers = register_and_login(api_client, "budget-set@example.com")
    project = api_client.post("/api/v1/projects", json={"name": "Budgeted"}, headers=headers).json()

    resp = api_client.patch(f"/api/v1/projects/{project['id']}/budget", json={"monthly_budget_usd": 500}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["monthly_budget_usd"] == 500

    resp = api_client.patch(f"/api/v1/projects/{project['id']}/budget", json={"monthly_budget_usd": None}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["monthly_budget_usd"] is None


def test_budget_status_surfaced_on_estimate_creation(api_client):
    _, headers = register_and_login(api_client, "budget-status@example.com")
    project = api_client.post("/api/v1/projects", json={"name": "Status Project"}, headers=headers).json()

    # No budget set yet -> budget_status is present but inert.
    resp = api_client.post(
        f"/api/v1/projects/{project['id']}/estimates", json={"requirement": COMPUTE_REQUIREMENT}, headers=headers,
    )
    assert resp.status_code == 201
    v1 = resp.json()
    assert v1["budget_status"]["budget_monthly"] is None
    assert v1["budget_status"]["within_budget"] is None
    actual = v1["result"]["cost"]["total_monthly"]

    # Set a budget well below actual cost -> next estimate should show an overage.
    api_client.patch(f"/api/v1/projects/{project['id']}/budget", json={"monthly_budget_usd": actual / 2}, headers=headers)
    resp = api_client.post(
        f"/api/v1/projects/{project['id']}/estimates", json={"requirement": COMPUTE_REQUIREMENT}, headers=headers,
    )
    v2 = resp.json()
    assert v2["budget_status"]["budget_monthly"] == actual / 2
    assert v2["budget_status"]["within_budget"] is False
    assert v2["budget_status"]["overage_amount"] > 0

    # Set a generous budget -> within budget.
    api_client.patch(f"/api/v1/projects/{project['id']}/budget", json={"monthly_budget_usd": actual * 10}, headers=headers)
    resp = api_client.post(
        f"/api/v1/projects/{project['id']}/estimates", json={"requirement": COMPUTE_REQUIREMENT}, headers=headers,
    )
    v3 = resp.json()
    assert v3["budget_status"]["within_budget"] is True
    assert v3["budget_status"]["overage_amount"] == 0


def test_budget_status_also_surfaced_on_reload_not_just_on_creation(api_client):
    """Regression test: a live QA pass found that GET
    /projects/{id}/estimates/{version} (reloading an already-saved version)
    always returned budget_status=null, even with a budget configured -
    only the response from the original POST that created the version
    computed it. Reloading a version later (e.g. the project detail page,
    or simply refreshing) must see the same budget-overage information."""
    _, headers = register_and_login(api_client, "budget-reload@example.com")
    project = api_client.post("/api/v1/projects", json={"name": "Reload Project"}, headers=headers).json()

    resp = api_client.post(
        f"/api/v1/projects/{project['id']}/estimates", json={"requirement": COMPUTE_REQUIREMENT}, headers=headers,
    )
    actual = resp.json()["result"]["cost"]["total_monthly"]

    api_client.patch(f"/api/v1/projects/{project['id']}/budget", json={"monthly_budget_usd": actual / 2}, headers=headers)

    resp = api_client.get(f"/api/v1/projects/{project['id']}/estimates/1", headers=headers)
    assert resp.status_code == 200
    reloaded = resp.json()
    assert reloaded["budget_status"] is not None
    assert reloaded["budget_status"]["budget_monthly"] == actual / 2
    assert reloaded["budget_status"]["within_budget"] is False
    assert reloaded["budget_status"]["overage_amount"] > 0


def test_other_user_cannot_set_budget(api_client):
    _, headers_a = register_and_login(api_client, "budget-owner@example.com")
    _, headers_b = register_and_login(api_client, "budget-intruder@example.com")
    project = api_client.post("/api/v1/projects", json={"name": "Owner Only"}, headers=headers_a).json()

    resp = api_client.patch(f"/api/v1/projects/{project['id']}/budget", json={"monthly_budget_usd": 100}, headers=headers_b)
    assert resp.status_code == 403


def test_compare_estimate_versions(api_client):
    _, headers = register_and_login(api_client, "compare-versions@example.com")
    project = api_client.post("/api/v1/projects", json={"name": "Comparable"}, headers=headers).json()

    api_client.post(f"/api/v1/projects/{project['id']}/estimates", json={"requirement": COMPUTE_REQUIREMENT}, headers=headers)
    bigger = dict(COMPUTE_REQUIREMENT, compute={"machine_family": "e2", "vcpu": 16, "ram_gb": 64, "instance_count": 1})
    api_client.post(f"/api/v1/projects/{project['id']}/estimates", json={"requirement": bigger}, headers=headers)

    resp = api_client.get(f"/api/v1/projects/{project['id']}/estimates/compare?from=1&to=2", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["from_version"] == 1
    assert body["to_version"] == 2
    assert body["delta_monthly"] > 0
    assert body["to_total_monthly"] > body["from_total_monthly"]
    assert "Compute" in body["category_deltas"]
    assert body["category_deltas"]["Compute"] > 0


def test_compare_estimate_versions_requires_existing_versions(api_client):
    _, headers = register_and_login(api_client, "compare-missing@example.com")
    project = api_client.post("/api/v1/projects", json={"name": "Empty"}, headers=headers).json()

    resp = api_client.get(f"/api/v1/projects/{project['id']}/estimates/compare?from=1&to=2", headers=headers)
    assert resp.status_code == 404
