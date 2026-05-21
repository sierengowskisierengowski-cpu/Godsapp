"""FastAPI REST server — off by default, binds 127.0.0.1.

Mirrors the CLI: list workspaces/tools/evidence, kick off scans, fetch results.
Token auth: file at ~/.config/godsapp/api.token containing the bearer token.
"""
from __future__ import annotations

import secrets
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel

from godsapp import __version__
from godsapp.core import evidence as ev_svc
from godsapp.core import paths
from godsapp.core import workspaces as ws_svc
from godsapp.core.health import check_health
from godsapp.core.scans import ScanRequest, runner
from godsapp.core.settings import load_settings
from godsapp.db import init_db
from godsapp.tools import registry


def _ensure_token() -> str:
    if not paths.API_TOKEN_PATH.exists():
        paths.ensure_directories()
        paths.API_TOKEN_PATH.write_text(secrets.token_urlsafe(32))
        try:
            paths.API_TOKEN_PATH.chmod(0o600)
        except OSError:
            pass
    return paths.API_TOKEN_PATH.read_text().strip()


def _require_token(authorization: Optional[str] = Header(None)) -> None:
    cfg = load_settings().api
    if not cfg.require_token:
        return
    token = _ensure_token()
    expected = f"Bearer {token}"
    if authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")


class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    target: Optional[str] = None


class ScanCreate(BaseModel):
    workspace_id: str
    tool: str
    target: str
    args: dict[str, Any] = {}


def create_app() -> FastAPI:
    init_db()
    registry.load_builtin()
    registry.load_plugins()

    app = FastAPI(title="GodsApp API", version=__version__)

    @app.get("/healthz")
    def healthz() -> dict:
        r = check_health()
        return {"ok": r.db_ok, "api": True, "db_url": r.db_url, "tools": r.tools}

    @app.get("/v1/workspaces", dependencies=[Depends(_require_token)])
    def workspaces_list() -> list[dict]:
        return [{"id": w.id, "name": w.name, "target": w.target,
                 "description": w.description,
                 "created_at": w.created_at.isoformat()}
                for w in ws_svc.list_workspaces()]

    @app.post("/v1/workspaces", dependencies=[Depends(_require_token)])
    def workspaces_create(body: WorkspaceCreate) -> dict:
        w = ws_svc.create_workspace(body.name, description=body.description, target=body.target)
        return {"id": w.id, "name": w.name}

    @app.get("/v1/tools", dependencies=[Depends(_require_token)])
    def tools_list() -> list[dict]:
        return [{"name": t.name, "title": t.title, "category": t.category,
                 "description": t.description,
                 "options": [opt.__dict__ for opt in t.options]}
                for t in registry.all()]

    @app.post("/v1/scans", dependencies=[Depends(_require_token)])
    async def scans_create(body: ScanCreate) -> dict:
        scan = await runner.run(ScanRequest(
            workspace_id=body.workspace_id, tool=body.tool,
            target=body.target, args=body.args))
        return {
            "id": scan.id,
            "status": scan.status,
            "exit_code": scan.exit_code,
            "findings": [
                {"title": f.title, "severity": f.severity, "host": f.host,
                 "port": f.port, "service": f.service}
                for f in scan.findings
            ],
        }

    @app.get("/v1/evidence", dependencies=[Depends(_require_token)])
    def evidence_list() -> list[dict]:
        return [{"sha256": e.sha256, "filename": e.filename,
                 "size_bytes": e.size_bytes, "mime_type": e.mime_type,
                 "created_at": e.created_at.isoformat()}
                for e in ev_svc.list_evidence()]

    return app


def serve(host: Optional[str] = None, port: Optional[int] = None) -> None:
    import uvicorn

    cfg = load_settings().api
    if cfg.require_token:
        _ensure_token()
    uvicorn.run(
        "godsapp.api.server:create_app",
        host=host or cfg.host,
        port=port or cfg.port,
        factory=True,
        log_level="info",
    )
