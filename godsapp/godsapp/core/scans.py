"""Scan runner: queue, execute, and persist tool invocations.

Tools are pluggable subclasses of `godsapp.tools.base.Tool`. The runner
streams stdout/stderr live to subscribers (UI/CLI) and persists the final
result + any parsed findings.
"""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from godsapp.core.audit import audit
from godsapp.core.logging import get_logger
from godsapp.db import Finding, Scan, get_session
from godsapp.tools import registry

log = get_logger(__name__)

# Subscribers receive (scan_id, kind, text) where kind in {"stdout","stderr","status"}.
LiveSubscriber = Callable[[str, str, str], None]


@dataclass
class ScanRequest:
    workspace_id: str
    tool: str
    target: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class FindingDTO:
    title: str
    severity: str
    host: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    service: Optional[str] = None
    description: Optional[str] = None


@dataclass
class CompletedScan:
    """Session-detached snapshot returned to UI / CLI / API."""
    id: str
    workspace_id: str
    tool: str
    target: str
    status: str
    exit_code: Optional[int]
    findings: list[FindingDTO] = field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class ScanRunner:
    def __init__(self) -> None:
        self._subscribers: list[LiveSubscriber] = []
        self._lock = threading.Lock()

    def subscribe(self, fn: LiveSubscriber) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(fn)
        def _unsub() -> None:
            with self._lock:
                if fn in self._subscribers:
                    self._subscribers.remove(fn)
        return _unsub

    def _emit(self, scan_id: str, kind: str, text: str) -> None:
        with self._lock:
            subs = list(self._subscribers)
        for fn in subs:
            try:
                fn(scan_id, kind, text)
            except Exception:
                log.exception("subscriber error")

    async def run(self, req: ScanRequest) -> CompletedScan:
        tool = registry.get(req.tool)
        if tool is None:
            raise ValueError(f"unknown tool: {req.tool}")

        with get_session() as s:
            scan = Scan(
                workspace_id=req.workspace_id,
                tool=req.tool,
                category=tool.category,
                target=req.target,
                args=req.args,
                status="running",
                started_at=datetime.utcnow(),
            )
            s.add(scan)
            s.flush()
            scan_id = scan.id
        # audit OUTSIDE the open transaction so SQLite never deadlocks on itself
        audit("scan.start", target=scan_id, data={"tool": req.tool, "target": req.target})
        self._emit(scan_id, "status", "running")

        stdout_buf: list[str] = []
        stderr_buf: list[str] = []

        def on_stdout(line: str) -> None:
            stdout_buf.append(line)
            self._emit(scan_id, "stdout", line)

        def on_stderr(line: str) -> None:
            stderr_buf.append(line)
            self._emit(scan_id, "stderr", line)

        exit_code = 1
        findings: list[dict[str, Any]] = []
        try:
            result = await tool.run(req.target, req.args, on_stdout=on_stdout, on_stderr=on_stderr)
            exit_code = result.exit_code
            findings = result.findings
        except FileNotFoundError as e:
            on_stderr(f"tool not installed: {e}\n")
        except Exception as e:
            log.exception("scan failed")
            on_stderr(f"error: {e}\n")

        status = "completed" if exit_code == 0 else "failed"
        # Persist + build a detached DTO inside the same session so consumers
        # (UI/CLI/API) never trip DetachedInstanceError on `.findings`.
        with get_session() as s:
            scan = s.get(Scan, scan_id)
            assert scan is not None
            scan.stdout = "".join(stdout_buf)
            scan.stderr = "".join(stderr_buf)
            scan.exit_code = exit_code
            scan.status = status
            scan.finished_at = datetime.utcnow()
            for f in findings:
                s.add(Finding(scan_id=scan_id, **f))
            s.flush()
            # Re-query with eager load and snapshot to plain dataclasses.
            scan_row = s.execute(
                select(Scan).where(Scan.id == scan_id).options(selectinload(Scan.findings))
            ).scalar_one()
            dto = CompletedScan(
                id=scan_row.id,
                workspace_id=scan_row.workspace_id,
                tool=scan_row.tool,
                target=scan_row.target,
                status=scan_row.status,
                exit_code=scan_row.exit_code,
                started_at=scan_row.started_at,
                finished_at=scan_row.finished_at,
                findings=[
                    FindingDTO(
                        title=f.title, severity=f.severity, host=f.host,
                        port=f.port, protocol=f.protocol, service=f.service,
                        description=f.description,
                    )
                    for f in scan_row.findings
                ],
            )

        self._emit(scan_id, "status", status)
        audit("scan.finish", target=scan_id, data={"exit_code": exit_code, "findings": len(findings)})
        return dto

    def run_sync(self, req: ScanRequest) -> CompletedScan:
        return asyncio.run(self.run(req))


runner = ScanRunner()
