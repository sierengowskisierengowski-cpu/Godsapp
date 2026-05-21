"""JSON helpers that always handle datetime/Path/etc.

Meli lesson: json.dumps() on data containing datetime objects crashes unless
you pass default=str. This module centralises that so we never miss it.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID


def _default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return str(value)


def dumps(obj: Any, *, indent: int | None = None) -> str:
    return json.dumps(obj, default=_default, indent=indent, ensure_ascii=False)


def loads(s: str | bytes) -> Any:
    return json.loads(s)
