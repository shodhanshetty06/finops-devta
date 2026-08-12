"""Persists versioned estimate snapshots plus a queryable audit trail.

Each save writes the full request and full computed result as JSON (so a
past estimate can be reloaded or re-exported to Excel/PDF without ever
re-running the pricing engine) AND expands `audit_log.entries` into
individual `AuditLogRowModel` rows (so the audit trail can be queried/
reported on directly, per the FinOps platform's "audit log" requirement)."""
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import AuditLogRowModel, EstimateVersionModel
from app.domain.estimate import EstimateResult
from app.domain.requirements import CustomerRequirement


class EstimateVersionRepository:
    def __init__(self, db: Session):
        self.db = db

    def next_version_number(self, project_id: int) -> int:
        stmt = select(func.max(EstimateVersionModel.version)).where(EstimateVersionModel.project_id == project_id)
        current_max = self.db.execute(stmt).scalar_one_or_none()
        return (current_max or 0) + 1

    def add_version(
        self, *, project_id: int, requirement: CustomerRequirement, result: EstimateResult, created_by_id: int,
    ) -> EstimateVersionModel:
        version_number = self.next_version_number(project_id)

        row = EstimateVersionModel(
            project_id=project_id,
            version=version_number,
            estimate_id=result.estimate_id,
            request_json=requirement.model_dump(mode="json"),
            result_json=result.model_dump(mode="json"),
            total_monthly=result.cost.total_monthly,
            currency=result.cost.currency,
            created_by_id=created_by_id,
        )
        self.db.add(row)
        self.db.flush()  # assigns row.id without committing yet

        for entry in result.audit_log.entries:
            self.db.add(AuditLogRowModel(
                estimate_version_id=row.id,
                timestamp=entry.timestamp,
                actor=entry.actor,
                action=entry.action,
                field=entry.field,
                detail=entry.detail,
            ))

        self.db.commit()
        self.db.refresh(row)
        return row

    def list_versions(self, project_id: int) -> list[EstimateVersionModel]:
        stmt = (
            select(EstimateVersionModel)
            .where(EstimateVersionModel.project_id == project_id)
            .order_by(EstimateVersionModel.version.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_version(self, project_id: int, version: int) -> EstimateVersionModel | None:
        stmt = select(EstimateVersionModel).where(
            EstimateVersionModel.project_id == project_id,
            EstimateVersionModel.version == version,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_latest(self, project_id: int) -> EstimateVersionModel | None:
        stmt = (
            select(EstimateVersionModel)
            .where(EstimateVersionModel.project_id == project_id)
            .order_by(EstimateVersionModel.version.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def delete_audit_rows_older_than(self, cutoff: datetime) -> int:
        """Retention sweep for the queryable audit trail (AuditLogRowModel).
        Leaves `result_json`/`request_json` on the estimate version itself
        untouched - only the expanded, admin-only audit rows are purged."""
        stmt = delete(AuditLogRowModel).where(AuditLogRowModel.timestamp < cutoff)
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount or 0
