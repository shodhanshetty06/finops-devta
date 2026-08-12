"""Declarative base shared by every ORM model. Kept in its own module (rather
than alongside the models) so Alembic's `env.py` can import just the
metadata without pulling in the rest of the app."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
