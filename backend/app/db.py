"""Database engine / session management.

SQLite by default for local development; point DATABASE_URL at PostgreSQL
in production (``postgres://`` URLs from Render/Railway/Heroku are normalized
to ``postgresql+psycopg2://`` in :mod:`app.config`). Tables are created
automatically on startup (see README for the Alembic/migration path when
evolving the schema in production).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings, normalize_database_url


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def _sqlite_file_path(url: str) -> Path | None:
    """Extract the file path from a sqlite URL (None for in-memory URLs)."""
    raw = url.split(":///", 1)[-1] if url.startswith("sqlite:///") else ""
    if not raw or raw == ":memory:" or raw.startswith("?"):
        return None
    return Path(raw).expanduser()


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        url = normalize_database_url(settings.database_url)
        kwargs: dict = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            # Create the parent directory so `sqlite:////data/x.db` never fails
            # on a fresh container/disk where only the mount point exists.
            path = _sqlite_file_path(url)
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            # PaaS Postgres: recycle connections before the platform drops idle
            # ones (Render/Railway close after ~60-300s), keep the pool small so
            # a free/starter instance never exhausts the DB's connection limit.
            kwargs["pool_recycle"] = 280
            if "nullpool" not in url.lower():
                kwargs.update(pool_size=5, max_overflow=5, pool_timeout=30)
        _engine = create_engine(url, **kwargs)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def init_db() -> None:
    # Import models so they register with Base.metadata
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


def get_db():
    """FastAPI dependency yielding a DB session."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()
