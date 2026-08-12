"""
Engine/session factory + FastAPI dependency.

SQLite by default (zero-setup local dev/tests), Postgres in production via
`FINOPS_DATABASE_URL` (see docker-compose.yml). Repositories and services
only ever depend on a SQLAlchemy `Session`, never on this module directly,
so the backend swap is transparent to the rest of the app.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
