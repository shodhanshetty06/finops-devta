"""Scheduled retention sweep for the queryable audit trail
(AuditLogRowModel). Run daily via Celery beat (see celery_app.py's
`beat_schedule`) - not exposed as an API endpoint, since this is routine
housekeeping rather than a user- or admin-triggered action.
"""
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.estimate_repository import EstimateVersionRepository
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.audit_tasks.purge_expired_audit_logs_task")
def purge_expired_audit_logs_task() -> dict[str, int]:
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.audit_log_retention_days)

    db = SessionLocal()
    try:
        deleted = EstimateVersionRepository(db).delete_audit_rows_older_than(cutoff)
    finally:
        db.close()

    return {"deleted": deleted}
