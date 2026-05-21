"""Database engine + session management.

Defaults to SQLite at ~/.local/share/godsapp/godsapp.db. Power users can set
GODSAPP_DATABASE_URL (or `[database].url` in settings.toml) to point at an
existing PostgreSQL instance for larger datasets.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from godsapp.core import paths
from godsapp.core.settings import load_settings

_engine: Optional[Engine] = None
_Session: Optional[sessionmaker] = None


def _resolve_url() -> str:
    env = os.environ.get("GODSAPP_DATABASE_URL")
    if env:
        return env
    settings_url = load_settings().database.url
    if settings_url:
        return settings_url
    paths.ensure_directories()
    return f"sqlite:///{paths.DB_PATH}"


def get_engine() -> Engine:
    global _engine, _Session
    if _engine is not None:
        return _engine
    url = _resolve_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, echo=False, future=True, connect_args=connect_args)

    if url.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()

    _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def init_db() -> None:
    """Create all tables. Idempotent."""
    from godsapp.db.models import Base
    engine = get_engine()
    Base.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    if _Session is None:
        get_engine()
    assert _Session is not None
    sess = _Session()
    try:
        yield sess
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()
