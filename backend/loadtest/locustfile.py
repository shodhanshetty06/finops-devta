"""Load test scenario for the FinOps API, run with Locust.

Exercises the two most expensive request shapes in the platform under
concurrent load:

  - POST /api/v1/estimate (stateless): the full validate -> normalize ->
    price -> assumption-log pipeline, unauthenticated, no DB write. This is
    the hottest path in the whole app - every questionnaire submission and
    every optimization-engine call re-runs it internally.
  - POST /api/v1/optimization/compare-clouds: the above pipeline run three
    times (once per cloud provider) in a single request - the most
    CPU-expensive single endpoint in the platform.

A registered-user journey (register once per simulated user, then repeatedly
create project estimates) is included too, to put write load on the DB
alongside the read-heavy pricing load.

Usage: see docs/LOAD_TEST_RESULTS.md for how this was run and the recorded
baseline numbers. Quick start:

    locust -f loadtest/locustfile.py --host http://127.0.0.1:PORT \
        --headless -u 50 -r 10 -t 60s --csv loadtest/results/run
"""
import random
import time

from locust import HttpUser, task, between, events

COMPUTE_REQUIREMENT = {
    "project_name": "Load Test",
    "region": "us-central1",
    "normalization_strategy": "balanced",
    "compute": {"machine_family": "n2", "vcpu": 4, "ram_gb": 16, "instance_count": 2},
    "storage": {"disk_type": "pd-balanced", "size_gb": 200, "snapshot_enabled": True},
    "database": {"required": True, "engine": "postgres", "size_gb": 50, "vcpu": 2, "ram_gb": 8},
    "network": {"load_balancer_required": True, "external_ip_count": 1, "estimated_egress_gb_per_month": 300},
}


def _jittered_requirement() -> dict:
    """Vary vCPU/instance count per request so responses aren't served from
    any accidental in-process memoization - keeps the benchmark honest."""
    req = {**COMPUTE_REQUIREMENT, "compute": {
        **COMPUTE_REQUIREMENT["compute"],
        "vcpu": random.choice([2, 4, 8, 16]),
        "instance_count": random.choice([1, 2, 3]),
    }}
    return req


class AnonymousEstimateUser(HttpUser):
    """Simulates the public/stateless estimate endpoint - the highest-
    traffic, unauthenticated part of the API. All `/api/v1/optimization/*`
    endpoints (including compare-clouds) require auth (see
    api/routers/optimization.py, `Depends(get_current_user)` on every
    route) so that traffic lives in RegisteredUserJourney below, not here."""
    weight = 3
    wait_time = between(0.5, 2.0)

    @task
    def stateless_estimate(self):
        self.client.post("/api/v1/estimate", json=_jittered_requirement(), name="/api/v1/estimate")


class RegisteredUserJourney(HttpUser):
    """Simulates a logged-in customer creating projects and estimate
    versions - puts write load on the DB alongside the read-heavy pricing
    load above."""
    weight = 1
    wait_time = between(1.0, 3.0)

    def on_start(self):
        email = f"loadtest-{int(time.time() * 1000)}-{random.randint(0, 1_000_000)}@example.com"
        password = "loadtestpassword123"
        resp = self.client.post("/api/v1/auth/register", json={
            "email": email, "password": password, "full_name": "Load Test User", "role": "customer",
        }, name="/api/v1/auth/register")
        if resp.status_code != 201:
            self.environment.runner.quit()
            return
        resp = self.client.post(
            "/api/v1/auth/login", data={"username": email, "password": password}, name="/api/v1/auth/login",
        )
        token = resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {token}"}
        resp = self.client.post("/api/v1/projects", json={"name": "Load Test Project"},
                                 headers=self.headers, name="/api/v1/projects [create]")
        self.project_id = resp.json()["id"]

    @task(3)
    def create_estimate_version(self):
        self.client.post(
            f"/api/v1/projects/{self.project_id}/estimates",
            json={"requirement": _jittered_requirement()},
            headers=self.headers,
            name="/api/v1/projects/{id}/estimates [create version]",
        )

    @task(1)
    def compare_clouds(self):
        self.client.post(
            "/api/v1/optimization/compare-clouds",
            json={"requirement": _jittered_requirement()},
            headers=self.headers,
            name="/api/v1/optimization/compare-clouds",
        )


@events.quitting.add_listener
def _print_summary(environment, **kwargs):
    stats = environment.stats.total
    print(
        f"\n--- Load test summary ---\n"
        f"requests={stats.num_requests} failures={stats.num_failures} "
        f"median_ms={stats.median_response_time} p95_ms={stats.get_response_time_percentile(0.95)} "
        f"p99_ms={stats.get_response_time_percentile(0.99)} rps={stats.total_rps:.2f}\n"
    )
