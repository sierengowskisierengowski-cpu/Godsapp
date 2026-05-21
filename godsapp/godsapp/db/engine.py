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
    """Create all tables and apply lightweight in-place schema upgrades.

    We use add-if-missing ALTERs instead of a full Alembic migration because
    SQLite is the default and the user runs this on a single workstation —
    nobody wants to debug alembic locally on a desktop tool. Idempotent.
    """
    from sqlalchemy import inspect, text
    from godsapp.db.models import Base
    engine = get_engine()
    Base.metadata.create_all(engine)
    _ensure_columns(engine)


def _ensure_columns(engine: Engine) -> None:
    """Add columns that older databases may be missing."""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if not insp.has_table("findings"):
        return
    existing = {c["name"] for c in insp.get_columns("findings")}
    additions = [
        ("status",           "VARCHAR(16) DEFAULT 'open'"),
        ("cvss_score",       "FLOAT"),
        ("cve_ids",          "VARCHAR(255)"),
        ("mitre_technique",  "VARCHAR(64)"),
        ("tags",             "VARCHAR(255)"),
    ]
    with engine.begin() as conn:
        for col, ddl in additions:
            if col not in existing:
                try:
                    conn.execute(text(f"ALTER TABLE findings ADD COLUMN {col} {ddl}"))
                except Exception:
                    pass  # already exists on a race or unsupported dialect


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
