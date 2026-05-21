"""Tool registry: built-in tools register at import time, plugins via discovery."""
from __future__ import annotations

import importlib
import pkgutil
from typing import Optional

from godsapp.core.logging import get_logger
from godsapp.tools.base import Tool

log = get_logger(__name__)


class _Registry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError("tool.name is required")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return sorted(self._tools.values(), key=lambda t: (t.category, t.name))

    def by_category(self) -> dict[str, list[Tool]]:
        out: dict[str, list[Tool]] = {}
        for t in self.all():
            out.setdefault(t.category, []).append(t)
        return out

    def load_builtin(self) -> None:
        """Walk godsapp.tools.* and import every submodule so tools self-register."""
        import godsapp.tools as pkg
        for mod in pkgutil.walk_packages(pkg.__path__, prefix="godsapp.tools."):
            if mod.name in {"godsapp.tools.base", "godsapp.tools.registry"}:
                continue
            try:
                importlib.import_module(mod.name)
            except Exception:
                log.exception("failed to load tool module %s", mod.name)

    def load_plugins(self) -> None:
        """Discover and import user plugins under ~/.local/share/godsapp/plugins/.

        Each plugin is a Python package directory. We add the plugin dir to
        sys.path and import every subdirectory as a module.
        """
        import sys

        from godsapp.core import paths
        if not paths.PLUGIN_DIR.exists():
            return
        sys.path.insert(0, str(paths.PLUGIN_DIR))
        for entry in paths.PLUGIN_DIR.iterdir():
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            try:
                importlib.import_module(entry.name)
            except Exception:
                log.exception("failed to load plugin %s", entry.name)


registry = _Registry()
