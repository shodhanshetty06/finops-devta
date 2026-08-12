"""
AI Recommendation Engine.

When a customer supplies only business-level requirements (user counts,
uptime targets, "I need a database") instead of concrete infrastructure
specs, this engine fills in the missing CustomerRequirement sections with
reasonable defaults - it does NOT invent pricing (that still comes from
PricingProvider) and every inference it makes is returned as an Assumption
with strategy_applied="ai_recommendation" so it's fully visible downstream.

This is heuristic/rule-based today. A future phase can swap the scoring
function for an LLM-backed extractor without changing the calling contract:
`recommend(requirement) -> (CustomerRequirement, list[Assumption])`.
"""
from app.domain.assumption import Assumption
from app.domain.enums import CloudSqlEngine, MachineFamily
from app.domain.requirements import (
    ComputeRequirement,
    DatabaseRequirement,
    KubernetesRequirement,
    NetworkRequirement,
)
from app.domain.requirements import CustomerRequirement


class RecommendationEngine:
    def recommend(self, requirement: CustomerRequirement) -> tuple[CustomerRequirement, list[Assumption]]:
        req = requirement.model_copy(deep=True)
        assumptions: list[Assumption] = []

        biz = req.business
        users = 0
        if biz is not None:
            users = max(biz.peak_concurrent_users or 0, biz.total_users or 0)

        wants_ha = bool(req.availability and req.availability.high_availability)
        high_uptime = bool(req.availability and req.availability.target_uptime_percent and req.availability.target_uptime_percent >= 99.9)

        if req.compute is None:
            vcpu, ram, instances, family = self._size_compute(users, wants_ha or high_uptime)
            req.compute = ComputeRequirement(machine_family=family, vcpu=vcpu, ram_gb=ram, instance_count=instances)
            assumptions.append(Assumption(
                field="compute",
                requested_value="(not provided - business requirements only)",
                used_value=f"{family.value}: {vcpu} vCPU / {ram} GB x {instances} instance(s)",
                reason=f"Inferred compute sizing from business context (~{users or 'unspecified'} users, HA={wants_ha or high_uptime}).",
                strategy_applied="ai_recommendation",
            ))

        needs_lb = users > 100 or wants_ha or high_uptime
        if needs_lb and (req.network is None or not req.network.load_balancer_required):
            req.network = req.network or NetworkRequirement()
            if not req.network.load_balancer_required:
                req.network.load_balancer_required = True
                req.network.external_ip_count = max(req.network.external_ip_count, 1)
                assumptions.append(Assumption(
                    field="network.load_balancer_required",
                    requested_value="(not provided)",
                    used_value="true",
                    reason="Load balancer recommended for multi-instance / HA / uptime-sensitive deployments.",
                    strategy_applied="ai_recommendation",
                ))

        if req.database is None and (users > 500 or wants_ha):
            db_vcpu, db_ram = (4, 16) if users > 5000 else (2, 8)
            req.database = DatabaseRequirement(
                required=True,
                engine=CloudSqlEngine.POSTGRES,
                size_gb=100,
                vcpu=db_vcpu,
                ram_gb=db_ram,
                high_availability=wants_ha or high_uptime,
            )
            assumptions.append(Assumption(
                field="database",
                requested_value="(not provided - business requirements only)",
                used_value=f"Cloud SQL postgres, {db_vcpu} vCPU / {db_ram} GB, 100 GB storage, HA={wants_ha or high_uptime}",
                reason="Business context implies a persistent application database; defaulted to a 100 GB PostgreSQL instance.",
                strategy_applied="ai_recommendation",
            ))

        if req.kubernetes is None and users > 5000:
            req.kubernetes = KubernetesRequirement(required=True, node_count=3, autopilot=True)
            assumptions.append(Assumption(
                field="kubernetes",
                requested_value="(not provided)",
                used_value="GKE Autopilot, 3-node baseline",
                reason=f"Scale (~{users} users) warrants container orchestration for elastic scaling.",
                strategy_applied="ai_recommendation",
            ))

        return req, assumptions

    @staticmethod
    def _size_compute(users: int, needs_headroom: bool) -> tuple[int, float, int, MachineFamily]:
        if users <= 100:
            vcpu, ram, instances = 2, 8.0, 1
        elif users <= 1000:
            vcpu, ram, instances = 4, 16.0, 2
        elif users <= 10000:
            vcpu, ram, instances = 8, 32.0, 3
        else:
            vcpu, ram, instances = 16, 64.0, 5

        family = MachineFamily.N2 if (needs_headroom or users > 1000) else MachineFamily.E2
        if needs_headroom and instances < 2:
            instances = 2  # avoid a single point of failure when HA/uptime is requested
        return vcpu, ram, instances, family
