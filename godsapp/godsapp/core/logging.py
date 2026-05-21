"""Application logging with rotation to ~/.local/share/godsapp/logs/."""
from __future__ import annotations

import logging
import logging.handlers
import sys
from typing import Optional

from godsapp.core import paths

_CONFIGURED = False


def setup_logging(level: int = logging.INFO, *, console: bool = True) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    paths.ensure_directories()

    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.handlers.RotatingFileHandler(
        paths.LOG_DIR / "godsapp.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    if console:
        ch = logging.StreamHandler(sys.stderr)
        ch.setFormatter(fmt)
        root.addHandler(ch)

    _CONFIGURED = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name or "godsapp")
