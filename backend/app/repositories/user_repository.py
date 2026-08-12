"""Repository pattern: isolates SQLAlchemy query code from services. Services
depend on this class, never on `Session`/ORM query syntax directly, so the
persistence mechanism could be swapped without touching business logic."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import UserModel


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> UserModel | None:
        return self.db.get(UserModel, user_id)

    def get_by_email(self, email: str) -> UserModel | None:
        stmt = select(UserModel).where(UserModel.email == email)
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, *, email: str, hashed_password: str, full_name: str, role: str) -> UserModel:
        user = UserModel(email=email, hashed_password=hashed_password, full_name=full_name, role=role)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def list_all(self) -> list[UserModel]:
        return list(self.db.execute(select(UserModel)).scalars().all())
