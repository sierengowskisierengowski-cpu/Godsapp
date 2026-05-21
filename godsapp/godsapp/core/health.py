"""Backend health snapshot — surfaced in the UI header (Meli lesson).

If the DB or a critical tool is unreachable, the user sees it instead of
buttons silently doing nothing.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass

from sqlalchemy import text

from godsapp.db import get_engine


@dataclass
class HealthReport:
    db_ok: bool
    db_url: str
    tools: dict[str, bool]
    api_running: bool


# Tools we shell out to. Missing tools are surfaced in the UI rather than crashing.
EXTERNAL_TOOLS = [
    "nmap", "hashcat", "hydra", "sqlmap", "nikto", "gobuster",
    "wpscan", "tcpdump", "tshark", "masscan", "amass", "subfinder",
    "ffuf", "whatweb", "dnsrecon", "theharvester", "metasploit",
]


def check_health() -> HealthReport:
    engine = get_engine()
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    tools = {t: shutil.which(t) is not None for t in EXTERNAL_TOOLS}

    api_running = False
    try:
        import httpx
        from godsapp.core.settings import load_settings
        cfg = load_settings().api
        r = httpx.get(f"http://{cfg.host}:{cfg.port}/healthz", timeout=0.2)
        api_running = r.status_code == 200
    except Exception:
        api_running = False

    return HealthReport(db_ok=db_ok, db_url=str(engine.url), tools=tools, api_running=api_running)
