"""Evidence locker with SHA-256 content addressing and chain of custody.

Files land at ~/.local/share/godsapp/evidence/<sha256[:2]>/<sha256>.<ext>
so duplicate content collapses and integrity is verifiable.
"""
from __future__ import annotations

import hashlib
import mimetypes
import shutil
from pathlib import Path
from typing import Optional

from sqlalchemy import select

from godsapp.core import paths
from godsapp.core.audit import audit
from godsapp.db import CustodyChain, Evidence, get_session


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def store_file(
    source: Path,
    *,
    scan_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    note: Optional[str] = None,
    actor: str = "local-user",
) -> Evidence:
    """Copy `source` into the evidence locker and register it."""
    paths.ensure_directories()
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    sha = _hash_file(source)
    sub = paths.EVIDENCE_DIR / sha[:2]
    sub.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix
    dest = sub / (sha + suffix)
    if not dest.exists():
        shutil.copy2(source, dest)

    size = dest.stat().st_size
    mime, _ = mimetypes.guess_type(source.name)
    rel = str(dest.relative_to(paths.EVIDENCE_DIR))

    with get_session() as s:
        existing = s.execute(select(Evidence).where(Evidence.sha256 == sha)).scalar_one_or_none()
        if existing is not None:
            ev = existing
            ev_id = ev.id
            is_dup = True
        else:
            ev = Evidence(
                scan_id=scan_id,
                workspace_id=workspace_id,
                filename=source.name,
                relative_path=rel,
                mime_type=mime,
                size_bytes=size,
                sha256=sha,
                note=note,
            )
            s.add(ev)
            s.flush()
            ev_id = ev.id
            is_dup = False
        s.add(CustodyChain(
            evidence_id=ev_id,
            actor=actor,
            action="ingest-duplicate" if is_dup else "ingest",
            note=note,
            sha256_at_time=sha,
        ))
    # audit after the session commits to avoid SQLite write contention
    audit("evidence.ingest", target=sha, data={"filename": source.name, "size": size})
    with get_session() as s:
        return s.get(Evidence, ev_id)  # type: ignore[return-value]


def list_evidence(*, workspace_id: Optional[str] = None) -> list[Evidence]:
    with get_session() as s:
        q = select(Evidence).order_by(Evidence.created_at.desc())
        if workspace_id:
            q = q.where(Evidence.workspace_id == workspace_id)
        return list(s.execute(q).scalars().all())


def absolute_path(ev: Evidence) -> Path:
    return paths.EVIDENCE_DIR / ev.relative_path


def verify(ev: Evidence) -> bool:
    """Re-hash the file and compare to the stored sha256."""
    p = absolute_path(ev)
    if not p.is_file():
        return False
    return _hash_file(p) == ev.sha256
