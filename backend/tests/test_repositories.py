"""Repository-layer tests, exercised directly against a Session (no HTTP
layer) - proves the repository pattern works independent of FastAPI, and
that services could be unit tested the same way."""
from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.db.models import AuditLogRowModel
from app.repositories.estimate_repository import EstimateVersionRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.user_repository import UserRepository


def test_user_repository_create_and_lookup(db_session):
    repo = UserRepository(db_session)
    user = repo.create(email="repo-user@example.com", hashed_password=hash_password("pw"), full_name="Repo User", role="customer")
    assert user.id is not None

    fetched = repo.get_by_email("repo-user@example.com")
    assert fetched.id == user.id
    assert repo.get_by_id(user.id).email == "repo-user@example.com"
    assert repo.get_by_email("nobody@example.com") is None


def test_project_repository_owner_scoping(db_session):
    users = UserRepository(db_session)
    owner1 = users.create(email="p1@example.com", hashed_password="x", full_name="P1", role="consultant")
    owner2 = users.create(email="p2@example.com", hashed_password="x", full_name="P2", role="consultant")

    projects = ProjectRepository(db_session)
    projects.create(name="Owner1 Project A", owner_id=owner1.id)
    projects.create(name="Owner1 Project B", owner_id=owner1.id)
    projects.create(name="Owner2 Project", owner_id=owner2.id)

    assert len(projects.list_for_owner(owner1.id)) == 2
    assert len(projects.list_for_owner(owner2.id)) == 1
    assert len(projects.list_all()) == 3


def test_estimate_repository_versions_and_audit_rows(db_session, sample_estimate):
    users = UserRepository(db_session)
    user = users.create(email="est-owner@example.com", hashed_password="x", full_name="Est Owner", role="consultant")
    projects = ProjectRepository(db_session)
    project = projects.create(name="Versioned", owner_id=user.id)

    estimates = EstimateVersionRepository(db_session)
    assert estimates.next_version_number(project.id) == 1

    v1 = estimates.add_version(
        project_id=project.id, requirement=sample_estimate.original_request, result=sample_estimate, created_by_id=user.id,
    )
    assert v1.version == 1
    assert len(v1.audit_rows) == len(sample_estimate.audit_log.entries)

    v2 = estimates.add_version(
        project_id=project.id, requirement=sample_estimate.original_request, result=sample_estimate, created_by_id=user.id,
    )
    assert v2.version == 2

    versions = estimates.list_versions(project.id)
    assert [v.version for v in versions] == [2, 1]

    assert estimates.get_version(project.id, 1).id == v1.id
    assert estimates.get_latest(project.id).id == v2.id
    assert estimates.get_version(project.id, 99) is None


def test_delete_audit_rows_older_than_only_purges_stale_rows(db_session, sample_estimate):
    users = UserRepository(db_session)
    user = users.create(email="retention-owner@example.com", hashed_password="x", full_name="Retention Owner", role="consultant")
    projects = ProjectRepository(db_session)
    project = projects.create(name="Retention", owner_id=user.id)

    estimates = EstimateVersionRepository(db_session)
    version = estimates.add_version(
        project_id=project.id, requirement=sample_estimate.original_request, result=sample_estimate, created_by_id=user.id,
    )
    fresh_count = len(version.audit_rows)
    assert fresh_count > 0

    # Backdate half the rows past the retention window; leave the rest fresh.
    stale_ids = [row.id for row in version.audit_rows[: fresh_count // 2 or 1]]
    db_session.query(AuditLogRowModel).filter(AuditLogRowModel.id.in_(stale_ids)).update(
        {"timestamp": datetime.now(timezone.utc) - timedelta(days=5)}, synchronize_session=False,
    )
    db_session.commit()

    cutoff = datetime.now(timezone.utc) - timedelta(days=2)
    deleted = estimates.delete_audit_rows_older_than(cutoff)
    assert deleted == len(stale_ids)

    remaining = db_session.query(AuditLogRowModel).filter(AuditLogRowModel.estimate_version_id == version.id).count()
    assert remaining == fresh_count - len(stale_ids)
