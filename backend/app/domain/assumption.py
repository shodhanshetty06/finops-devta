"""Assumption logging - the platform must never silently change a customer's
requested configuration. Every substitution made by the normalization engine
is recorded as an Assumption and surfaced everywhere (Excel, PDF, API, audit log)."""
from pydantic import BaseModel


class Assumption(BaseModel):
    field: str
    requested_value: str
    used_value: str
    reason: str
    strategy_applied: str | None = None
