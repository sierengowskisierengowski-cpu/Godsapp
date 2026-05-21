"""Smoke tests that don't require GTK to be importable.

Run with: pytest godsapp/tests/
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_dirs(monkeypatch):
    tmp = Path(tempfile.mkdtemp())
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp / "cache"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp / "state"))
    # Force settings/paths modules to rebuild against the new env
    import importlib
    from godsapp.core import paths as p
    importlib.reload(p)
    yield


def test_paths_resolve():
    from godsapp.core import paths
    paths.ensure_directories()
    assert paths.DATA_DIR.exists()
    assert paths.CONFIG_DIR.exists()


def test_jsonx_handles_datetime():
    from datetime import datetime
    from godsapp.core.jsonx import dumps
    s = dumps({"when": datetime(2026, 5, 21, 12, 0, 0)})
    assert "2026-05-21" in s


def test_db_initialises_and_workspace_crud():
    from godsapp.core import workspaces as ws
    from godsapp.db import init_db
    init_db()
    w = ws.create_workspace("test", target="example.com")
    assert w.id
    listed = ws.list_workspaces()
    assert any(x.id == w.id for x in listed)
    assert ws.delete_workspace(w.id) is True


def test_evidence_locker_hashes_and_dedupes(tmp_path):
    from godsapp.core import evidence as ev
    from godsapp.db import init_db
    init_db()
    p = tmp_path / "sample.txt"
    p.write_text("hello godsapp")
    e1 = ev.store_file(p)
    e2 = ev.store_file(p)  # duplicate ingest, same sha
    assert e1.sha256 == e2.sha256
    assert e1.id == e2.id
    assert ev.verify(e1) is True


def test_tool_registry_loads_builtin():
    from godsapp.tools import registry
    registry.load_builtin()
    names = [t.name for t in registry.all()]
    assert "nmap" in names
    assert "subdomain-brute" in names
    by_cat = registry.by_category()
    assert "recon" in by_cat
