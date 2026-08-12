"""Recommended architecture output produced by the Architecture Engine."""
from pydantic import BaseModel


class ArchitectureComponent(BaseModel):
    layer: str        # e.g. "Frontend", "Backend", "Database", "Networking", "Storage",
                       # "Load Balancer", "Monitoring", "Security", "Backup", "Disaster Recovery"
    service: str       # e.g. "GKE Autopilot", "Cloud SQL (PostgreSQL, HA)"
    rationale: str


class ArchitectureRecommendation(BaseModel):
    summary: str
    components: list[ArchitectureComponent]
