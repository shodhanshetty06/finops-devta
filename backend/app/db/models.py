"""
SQLAlchemy ORM models (Phase 3: persistence).

Deliberately separate from `app/domain/` - the domain layer's Pydantic
schemas are the API/business-logic vocabulary, these are the storage
vocabulary. Services translate between the two; nothing outside
`app/repositories/` and `app/services/` should import from this module.
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="customer")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    projects: Mapped[list["ProjectModel"]] = relationship(back_populates="owner")


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    # Phase 8: optional monthly budget ceiling, surfaced as `budget_status` on
    # every new estimate version so overages are visible the moment they happen.
    monthly_budget_usd: Mapped[float | None] = mapped_column(nullable=True)

    owner: Mapped["UserModel"] = relationship(back_populates="projects")
    estimate_versions: Mapped[list["EstimateVersionModel"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="EstimateVersionModel.version"
    )


class EstimateVersionModel(Base):
    """One saved, versioned snapshot of an estimate within a project. Storing
    both the original request and the full computed result means a past
    estimate can be reloaded or re-exported to Excel/PDF without ever
    re-running (and potentially getting different numbers from) the pricing
    engine."""

    __tablename__ = "estimate_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False)
    estimate_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    request_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    total_monthly: Mapped[float] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)

    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project: Mapped["ProjectModel"] = relationship(back_populates="estimate_versions")
    audit_rows: Mapped[list["AuditLogRowModel"]] = relationship(
        back_populates="estimate_version", cascade="all, delete-orphan"
    )


class AuditLogRowModel(Base):
    """Persisted, queryable form of each EstimateResult.audit_log entry -
    distinct from the JSON blob in `result_json` so the audit trail can be
    searched/reported on across estimates without deserializing every row."""

    __tablename__ = "audit_log_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    estimate_version_id: Mapped[int] = mapped_column(ForeignKey("estimate_versions.id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    field: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail: Mapped[str] = mapped_column(Text, nullable=False)

    estimate_version: Mapped["EstimateVersionModel"] = relationship(back_populates="audit_rows")
