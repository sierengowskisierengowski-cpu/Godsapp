"""Workspace CRUD shared by UI, CLI, and API."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from godsapp.core import paths
from godsapp.core.audit import audit
from godsapp.db import Workspace, get_session


def list_workspaces() -> list[Workspace]:
    with get_session() as s:
        rows = s.execute(select(Workspace).order_by(Workspace.created_at.desc())).scalars().all()
        return list(rows)


def get_workspace(workspace_id: str) -> Optional[Workspace]:
    with get_session() as s:
        return s.get(Workspace, workspace_id)


def create_workspace(
    name: str,
    description: Optional[str] = None,
    target: Optional[str] = None,
    color: str = "cream",
) -> Workspace:
    with get_session() as s:
        ws = Workspace(name=name, description=description, target=target, color=color)
        s.add(ws)
        s.flush()
        (paths.WORKSPACE_DIR / ws.id).mkdir(parents=True, exist_ok=True)
        ws_id = ws.id
    # audit AFTER the transaction commits — SQLite is single-writer and nesting
    # audit() inside an open session deadlocks under WAL contention.
    audit("workspace.create", target=ws_id, data={"name": name})
    return get_workspace(ws_id)  # type: ignore[return-value]


def update_workspace(
    workspace_id: str,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    target: Optional[str] = None,
    color: Optional[str] = None,
) -> Optional[Workspace]:
    with get_session() as s:
        ws = s.get(Workspace, workspace_id)
        if ws is None:
            return None
        if name is not None:
            ws.name = name
        if description is not None:
            ws.description = description
        if target is not None:
            ws.target = target
        if color is not None:
            ws.color = color
    audit("workspace.update", target=workspace_id)
    return get_workspace(workspace_id)


def delete_workspace(workspace_id: str) -> bool:
    with get_session() as s:
        ws = s.get(Workspace, workspace_id)
        if ws is None:
            return False
        s.delete(ws)
    audit("workspace.delete", target=workspace_id)
    return True
