from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ProjectModel


class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, name: str, owner_id: int) -> ProjectModel:
        project = ProjectModel(name=name, owner_id=owner_id)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def get_by_id(self, project_id: int) -> ProjectModel | None:
        return self.db.get(ProjectModel, project_id)

    def list_for_owner(self, owner_id: int) -> list[ProjectModel]:
        stmt = select(ProjectModel).where(ProjectModel.owner_id == owner_id).order_by(ProjectModel.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def list_all(self) -> list[ProjectModel]:
        stmt = select(ProjectModel).order_by(ProjectModel.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def update_budget(self, project: ProjectModel, monthly_budget_usd: float | None) -> ProjectModel:
        project.monthly_budget_usd = monthly_budget_usd
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project
