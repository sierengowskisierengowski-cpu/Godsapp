"""Background scheduler — runs `Schedule` rows on a cron-like cadence.

Cron expression: `minute hour day-of-month month day-of-week`.
Supports `*`, `*/N`, integer literals, `a-b` ranges, and comma lists.
Author: Joseph Sierengowski.
"""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select

from godsapp.core.audit import audit
from godsapp.core.logging import get_logger
from godsapp.core.scans import ScanRequest, runner
from godsapp.db import Schedule, get_session

log = get_logger(__name__)


def _match(field: str, val: int, lo: int) -> bool:
    for piece in field.split(","):
        piece = piece.strip()
        if piece in ("", "*"):
            return True
        if piece.startswith("*/"):
            try:
                step = int(piece[2:])
            except ValueError:
                continue
            if step > 0 and (val - lo) % step == 0:
                return True
            continue
        if "-" in piece:
            a, b = piece.split("-", 1)
            try:
                if int(a) <= val <= int(b):
                    return True
            except ValueError:
                continue
            continue
        try:
            if int(piece) == val:
                return True
        except ValueError:
            continue
    return False


def parse_cron(expr: str, now: datetime) -> datetime:
    """Return the next datetime ≥ now+1min satisfying the cron expression."""
    parts = (expr or "* * * * *").split()
    if len(parts) != 5:
        raise ValueError(f"cron must have 5 fields, got {expr!r}")
    minute, hour, dom, month, dow = parts
    candidate = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
    for _ in range(60 * 24 * 366):
        if (_match(minute, candidate.minute, 0)
            and _match(hour, candidate.hour, 0)
            and _match(dom, candidate.day, 1)
            and _match(month, candidate.month, 1)
            and _match(dow, candidate.weekday(), 0)):
            return candidate
        candidate += timedelta(minutes=1)
    raise ValueError("no future match within 1 year")


class SchedulerService:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._in_flight = 0
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="godsapp-scheduler",
        )
        self._thread.start()
        log.info("scheduler started")

    def stop(self) -> None:
        self._stop.set()
        log.info("scheduler stopping")

    def _loop(self) -> None:
        from godsapp.core.settings import load_settings
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                log.exception("scheduler tick failed")
            settings = load_settings()
            if not settings.scheduler.enabled:
                self._stop.wait(timeout=60)
                continue
            self._stop.wait(timeout=max(5, settings.scheduler.tick_seconds))

    def _tick(self) -> None:
        from godsapp.core.settings import load_settings
        max_par = max(1, load_settings().scheduler.max_concurrent)
        now = datetime.utcnow()
        due_ids: list[str] = []
        with get_session() as s:
            rows = s.execute(
                select(Schedule).where(Schedule.enabled == True)  # noqa: E712
            ).scalars().all()
            for r in rows:
                if r.next_run_at is None:
                    try:
                        r.next_run_at = parse_cron(r.cron, now)
                    except Exception:
                        log.warning("bad cron for schedule %s: %s", r.id, r.cron)
                        continue
                if r.next_run_at <= now:
                    due_ids.append(r.id)
        for sid in due_ids:
            with self._lock:
                if self._in_flight >= max_par:
                    log.info("scheduler: max concurrency reached, deferring %s", sid)
                    break
                self._in_flight += 1
            threading.Thread(
                target=self._fire, args=(sid, now), daemon=True,
                name=f"godsapp-sched-{sid[:8]}",
            ).start()

    def _fire(self, schedule_id: str, now: datetime) -> None:
        req: Optional[ScanRequest] = None
        try:
            with get_session() as s:
                r = s.get(Schedule, schedule_id)
                if r is None:
                    return
                req = ScanRequest(
                    workspace_id=r.workspace_id, tool=r.tool,
                    target=r.target, args=dict(r.args or {}),
                )
                r.last_run_at = now
                try:
                    r.next_run_at = parse_cron(r.cron, now)
                except Exception:
                    r.next_run_at = None
            audit("scheduler.fire", target=schedule_id,
                  data={"tool": req.tool, "target": req.target})
            asyncio.run(runner.run(req))
        except Exception:
            log.exception("scheduled scan failed: %s", schedule_id)
        finally:
            with self._lock:
                self._in_flight = max(0, self._in_flight - 1)


scheduler = SchedulerService()
