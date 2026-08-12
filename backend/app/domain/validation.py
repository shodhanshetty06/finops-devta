"""Validation result models. Every rule in the validation engine returns one
of these - never a bare bool - so that requested value, supported value,
reason, severity, and recommendation are always available downstream (API
response, Excel, PDF, dashboard, audit log)."""
from pydantic import BaseModel

from app.domain.enums import Severity


class ValidationResult(BaseModel):
    field: str                       # e.g. "compute.vcpu"
    rule: str                        # e.g. "cpu_validation"
    requested_value: str
    supported_value: str | None      # None if not applicable / not yet normalized
    is_valid: bool
    severity: Severity
    reason: str
    recommendation: str


class ValidationReport(BaseModel):
    results: list[ValidationResult]

    @property
    def has_blockers(self) -> bool:
        return any(r.severity == Severity.BLOCKER for r in self.results)

    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.results if r.severity == Severity.WARNING)

    @property
    def blocker_count(self) -> int:
        return sum(1 for r in self.results if r.severity == Severity.BLOCKER)
