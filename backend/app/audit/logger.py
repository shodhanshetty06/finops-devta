"""AuditLogger: accumulates an immutable, ordered trail of every decision made
while producing an estimate. This is what powers the Audit Log tab/sheet in
the dashboard, Excel export, and PDF export, and is also returned verbatim in
the API response so nothing is ever a "hidden" server-side decision."""
from app.domain.assumption import Assumption
from app.domain.audit import AuditLog, AuditLogEntry
from app.domain.pricing import CostBreakdown
from app.domain.validation import ValidationReport


class AuditLogger:
    def __init__(self, estimate_id: str):
        self._log = AuditLog(estimate_id=estimate_id)

    def record(self, action: str, detail: str, *, field: str | None = None, actor: str = "system", **metadata):
        self._log.entries.append(AuditLogEntry(action=action, detail=detail, field=field, actor=actor, metadata=metadata))

    def record_validation(self, report: ValidationReport):
        for r in report.results:
            self.record(
                "validation",
                r.reason,
                field=r.field,
                severity=r.severity.value,
                rule=r.rule,
                requested_value=r.requested_value,
                supported_value=r.supported_value,
            )

    def record_assumptions(self, assumptions: list[Assumption], actor: str = "system"):
        for a in assumptions:
            self.record(
                "normalization",
                a.reason,
                field=a.field,
                actor=actor,
                requested_value=a.requested_value,
                used_value=a.used_value,
                strategy=a.strategy_applied,
            )

    def record_pricing(self, cost: CostBreakdown):
        for li in cost.line_items:
            self.record(
                "pricing_lookup",
                f"{li.description}: {li.monthly_amount} {li.currency}/month",
                field=li.category,
                source=li.source,
                unit_price=li.unit_price,
                quantity=li.quantity,
            )
        for d in cost.discounts:
            self.record("discount_applied", f"{d.name}: -{d.monthly_savings} {cost.currency}/month ({d.percent_off}%)")

    @property
    def log(self) -> AuditLog:
        return self._log
