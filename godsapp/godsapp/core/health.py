"""Backend health snapshot — surfaced in the UI header (Meli lesson).

Tool detection delegates to ``godsapp.core.tool_detect`` so per-tool
override paths, alternate binary names (msfconsole vs metasploit), and
"out-of-PATH" install dirs (pipx venvs, ~/go/bin) are all honoured.

User-skipped tools (Settings → Tool Paths → "Skip") are still reported
truthfully in ``HealthReport.tools`` but flagged in ``skipped`` so the
dashboard counter can ignore them.

Author: Joseph Sierengowski.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import text

from godsapp.db import get_engine


@dataclass
class HealthReport:
    db_ok: bool
    db_url: str
    tools: dict[str, bool]              # tool_id → installed?
    api_running: bool
    tool_paths: dict[str, Optional[str]] = field(default_factory=dict)  # tool_id → resolved binary path
    skipped: set[str] = field(default_factory=set)                       # tool_ids the user has dismissed


def check_health() -> HealthReport:
    engine = get_engine()
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    # Delegated detection (catalog + override + extra dirs).
    from godsapp.core.settings import load_settings
    from godsapp.core.tool_detect import detect_all
    cfg = load_settings()
    overrides = dict(cfg.tool_paths.overrides)
    detections = detect_all(overrides=overrides)
    tools = {tid: d.found for tid, d in detections.items()}
    tool_paths = {tid: d.path for tid, d in detections.items()}
    skipped = set(cfg.tool_paths.skipped)

    api_running = False
    try:
        import httpx
        api = cfg.api
        r = httpx.get(f"http://{api.host}:{api.port}/healthz", timeout=0.2)
        api_running = r.status_code == 200
    except Exception:
        api_running = False

    return HealthReport(
        db_ok=db_ok,
        db_url=str(engine.url),
        tools=tools,
        api_running=api_running,
        tool_paths=tool_paths,
        skipped=skipped,
    )


# Kept for any legacy import sites — now derived from the catalog so it
# stays in sync without manual edits.
def _external_tools() -> list[str]:
    from godsapp.core.tool_catalog import all_ids
    return all_ids()


EXTERNAL_TOOLS = _external_tools()
