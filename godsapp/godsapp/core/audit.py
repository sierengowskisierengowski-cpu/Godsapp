"""Lightweight audit log helper."""
from __future__ import annotations

from typing import Any, Optional

from godsapp.db import AuditLog, get_session


def audit(event: str, *, target: Optional[str] = None, data: Optional[dict[str, Any]] = None,
          actor: str = "local-user") -> None:
    """Record an audit event. Never raises — auditing must not break operations."""
    try:
        with get_session() as s:
            s.add(AuditLog(event=event, target=target, data=data or {}, actor=actor))
    except Exception:
        # Avoid recursive audit. Logging will surface via the standard logger.
        from godsapp.core.logging import get_logger
        get_logger(__name__).exception("audit failed: %s", event)
