from app.domain.enums import Region
from app.domain.requirements import AvailabilityRequirement, BusinessContext, CustomerRequirement
from app.services.recommendation_engine import RecommendationEngine


def test_recommends_infrastructure_from_business_context_only():
    req = CustomerRequirement(
        project_name="Business-only project",
        region=Region.US_CENTRAL1,
        business=BusinessContext(total_users=500, peak_concurrent_users=500),
        availability=AvailabilityRequirement(high_availability=True, target_uptime_percent=99.99),
    )
    resolved, assumptions = RecommendationEngine().recommend(req)

    assert resolved.compute is not None
    assert resolved.compute.instance_count >= 2  # HA implies no single point of failure
    assert resolved.network is not None and resolved.network.load_balancer_required is True
    assert resolved.database is not None and resolved.database.high_availability is True
    assert len(assumptions) >= 3
    assert all(a.strategy_applied == "ai_recommendation" for a in assumptions)


def test_does_not_override_explicit_compute():
    from app.domain.requirements import ComputeRequirement
    from app.domain.enums import MachineFamily
    req = CustomerRequirement(
        project_name="Explicit project",
        region=Region.US_CENTRAL1,
        compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16),
        business=BusinessContext(total_users=50000),
    )
    resolved, assumptions = RecommendationEngine().recommend(req)
    assert resolved.compute.vcpu == 4  # untouched
    assert not any(a.field == "compute" for a in assumptions)
