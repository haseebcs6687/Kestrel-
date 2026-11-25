"""Database engine, session factory, and session dependency."""

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Lazily initialize and return the SQLAlchemy database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args: dict[str, Any] = {"connect_timeout": 2}
        _engine = create_engine(
            settings.get_database_url(),
            pool_pre_ping=True,
            connect_args=connect_args,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Lazily initialize and return the SQLAlchemy session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_factory


def get_db() -> Generator[Session]:
    """Yield a database session and guarantee its closure."""
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def reset_db_connections() -> None:
    """Reset engine and session factory caches (used in test teardown)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
