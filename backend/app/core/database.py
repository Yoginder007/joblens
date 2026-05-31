"""
Database engine, session factory, and declarative Base.

The engine is created lazily (on first session), not at import time — so models
and tooling can be imported without a live DB or driver present.

Two backends share the same models via dialect-aware column types
(see ``app.core.types``):
  - PostgreSQL (production): schema owned by Alembic migrations.
  - SQLite (local dev): schema created on startup via ``init_db()``.
"""
from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker | None = None


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        if settings.is_sqlite:
            _engine = create_engine(
                settings.database_url,
                echo=False,
                connect_args={"check_same_thread": False},
            )

            @event.listens_for(_engine, "connect")
            def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA journal_mode=WAL")
                cur.close()
        else:
            _engine = create_engine(
                settings.database_url,
                echo=False,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_pre_ping=True,
                connect_args={
                    "connect_timeout": 10,
                },
            )
    return _engine


def _factory() -> sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autocommit=False, autoflush=False
        )
    return _session_factory


def SessionLocal() -> Session:
    """Create a new session (used by Celery tasks outside the request cycle)."""
    return _factory()()


def init_db() -> None:
    """Create all tables (local/SQLite bootstrap). Postgres uses Alembic instead."""
    from app.db import base  # noqa: F401  (registers all models on metadata)

    Base.metadata.create_all(bind=get_engine())


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a session, rolls back on error, always closes."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
