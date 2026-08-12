"""
Celery application instance for the platform's async jobs (Phase 7):
report generation and batch estimate pricing, both of which can take long
enough - or run frequently enough in bulk - that they shouldn't block an
HTTP request/response cycle.

Redis (already required by Phase 5's SKU cache) serves as both broker and
result backend by default - one moving part instead of two for a platform
this size. `task_always_eager=True` (set via `FINOPS_CELERY_TASK_ALWAYS_EAGER`,
and unconditionally by `tests/conftest.py`) runs tasks synchronously
in-process with no broker/worker required at all, which is what makes the
test suite able to exercise these tasks without standing up Redis or a
worker process.
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "finops",
        broker=settings.resolved_celery_broker_url(),
        backend=settings.resolved_celery_result_backend(),
        include=["app.tasks.report_tasks", "app.tasks.batch_tasks", "app.tasks.audit_tasks"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        result_expires=settings.celery_result_expires_seconds,
        task_always_eager=settings.celery_task_always_eager,
        # Without this, eager-mode tasks never write their result to the
        # backend at all (Celery assumes the caller only ever needs the
        # AsyncResult object `.delay()` handed back directly). This
        # platform's jobs API instead looks results up later by id via a
        # fresh `AsyncResult(job_id)` - exactly how a real client polling
        # GET /api/v1/jobs/{id} works - so eager mode needs to persist to
        # the backend too, or that lookup pattern is untestable.
        task_store_eager_result=True,
        # False so a task exception is captured into the AsyncResult's
        # FAILURE state - exactly how a real broker/worker behaves - rather
        # than raised synchronously at the `.delay()` call site. Keeping
        # eager mode's failure semantics identical to production means the
        # "job failed, GET /jobs/{id} reports the error" path is actually
        # exercised by the test suite instead of bypassed.
        task_eager_propagates=False,
        task_track_started=True,
        timezone="UTC",
        # Requires a `celery -A app.tasks.celery_app.celery_app beat` process
        # running (see docker-compose.yml's celery-beat service / k8s's
        # celery-beat.yaml) - without it this schedule is registered but
        # nothing ever fires it, same as any other Celery task with no
        # worker. Runs daily (rather than every audit_log_retention_days) so
        # the actual retention window stays exactly what the setting says
        # regardless of how long the schedule itself has been running.
        beat_schedule={
            "purge-expired-audit-logs": {
                "task": "app.tasks.audit_tasks.purge_expired_audit_logs_task",
                "schedule": crontab(hour=3, minute=0),
            },
        },
    )
    return app


celery_app = create_celery_app()
