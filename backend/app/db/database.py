"""SQLAlchemy database primitives for future persistent domain models."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base class for future SQLAlchemy ORM models."""


@lru_cache
def get_engine():
    """Create the configured SQLAlchemy engine without opening a connection."""
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Build a session factory for request-scoped database access."""
    return sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)


def get_db_session() -> Generator[Session, None, None]:
    """Provide and close a database session for dependency injection."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_database_connectivity() -> bool:
    """Return whether the configured database accepts a simple query.

    The liveness endpoint intentionally does not call this helper. It exists
    for a future readiness endpoint without changing database primitives.
    """
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True
