"""Audit log entry - an immutable record of every decision the platform made
while producing an estimate (validation findings, normalization substitutions,
pricing lookups, discounts applied)."""
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class AuditLogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str = "system"           # "system" | "ai_recommendation_engine" | user id
    action: str                     # e.g. "validation", "normalization", "pricing_lookup"
    field: str | None = None
    detail: str
    metadata: dict = Field(default_factory=dict)


class AuditLog(BaseModel):
    estimate_id: str
    entries: list[AuditLogEntry] = Field(default_factory=list)
