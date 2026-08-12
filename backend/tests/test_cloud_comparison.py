"""Tests for the Phase 9 cross-cloud comparison engine and its API endpoint.
Unlike region/scenario comparison (Phase 8), this engine always builds its
own catalog/pricing provider pairs directly rather than depending on the
server's active FINOPS_CLOUD_PROVIDER setting - these tests don't need to
touch that setting at all."""
from app.core.config import Settings
from app.core.exceptions import FinOpsError
from app.domain.enums import MachineFamily, Region
from app.domain.requirements import ComputeRequirement, CustomerRequirement, StorageRequirement
from app.domain.enums import DiskType
from app.optimization.cloud_comparison_engine import CloudComparisonEngine
from tests.conftest import register_and_login

COMPUTE_REQUIREMENT = {
    "project_name": "Cloud Comparison Target",
    "region": "us-central1",
    "normalization_strategy": "balanced",
    "compute": {"machine_family": "n2", "vcpu": 4, "ram_gb": 16, "instance_count": 1},
    "storage": {"disk_type": "pd-balanced", "size_gb": 100},
}


def _requirement():
    return CustomerRequirement(
        project_name="Cloud Comparison Target",
        region=Region.US_CENTRAL1,
        normalization_strategy="balanced",
        compute=ComputeRequirement(machine_family=MachineFamily.N2, vcpu=4, ram_gb=16, instance_count=1),
        storage=StorageRequirement(disk_type=DiskType.PD_BALANCED, size_gb=100),
    )


def test_engine_compares_all_three_clouds_by_default():
    engine = CloudComparisonEngine()
    settings = Settings(default_normalization_strategy="balanced", default_tax_rate_percent=0, support_plan_percent=0)

    comparison = engine.compare(_requirement(), ["gcp", "aws", "azure"], settings)

    assert {o.cloud_provider for o in comparison.options} == {"gcp", "aws", "azure"}
    assert all(o.total_monthly > 0 for o in comparison.options)
    prices = {o.cloud_provider: o.total_monthly for o in comparison.options}
    cheapest = min(prices, key=prices.get)
    most_expensive = max(prices, key=prices.get)
    assert comparison.cheapest_cloud == cheapest
    assert comparison.most_expensive_cloud == most_expensive
    assert comparison.max_savings_monthly == round(prices[most_expensive] - prices[cheapest], 2)


def test_engine_reports_distinct_machine_types_per_cloud():
    engine = CloudComparisonEngine()
    settings = Settings()

    comparison = engine.compare(_requirement(), ["gcp", "aws", "azure"], settings)

    machine_types = {o.cloud_provider: o.primary_machine_type for o in comparison.options}
    assert machine_types["gcp"].startswith("n2-standard")
    assert machine_types["aws"].startswith("m5.")
    assert machine_types["azure"].startswith("Standard_D")


def test_engine_rejects_unsupported_cloud():
    engine = CloudComparisonEngine()
    settings = Settings()
    try:
        engine.compare(_requirement(), ["digitalocean"], settings)
        assert False, "expected FinOpsError"
    except FinOpsError as exc:
        assert exc.code == "unsupported_cloud_provider"


def test_compare_clouds_endpoint(api_client):
    _, headers = register_and_login(api_client, "cloud-compare@example.com")
    resp = api_client.post(
        "/api/v1/optimization/compare-clouds",
        json={"requirement": COMPUTE_REQUIREMENT},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["options"]) == 3
    assert body["cheapest_cloud"] in {"gcp", "aws", "azure"}


def test_compare_clouds_endpoint_accepts_subset(api_client):
    _, headers = register_and_login(api_client, "cloud-compare-subset@example.com")
    resp = api_client.post(
        "/api/v1/optimization/compare-clouds",
        json={"requirement": COMPUTE_REQUIREMENT, "clouds": ["gcp", "aws"]},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["options"]) == 2
    assert {o["cloud_provider"] for o in body["options"]} == {"gcp", "aws"}


def test_compare_clouds_endpoint_rejects_unknown_cloud(api_client):
    _, headers = register_and_login(api_client, "cloud-compare-bad@example.com")
    resp = api_client.post(
        "/api/v1/optimization/compare-clouds",
        json={"requirement": COMPUTE_REQUIREMENT, "clouds": ["digitalocean"]},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "unsupported_cloud_provider"


def test_compare_clouds_endpoint_requires_authentication(api_client):
    resp = api_client.post("/api/v1/optimization/compare-clouds", json={"requirement": COMPUTE_REQUIREMENT})
    assert resp.status_code == 401
