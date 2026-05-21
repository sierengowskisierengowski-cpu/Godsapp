"""Enumerate Python plugins from ~/.local/share/godsapp/plugins/.

Each plugin is a directory containing `plugin.toml` and a Python package.
Author: Joseph Sierengowski.
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from godsapp.core import paths


@dataclass
class PluginInfo:
    name: str
    path: Path
    version: str = "0.0.0"
    description: str = ""
    author: str = ""
    homepage: str = ""
    enabled: bool = True
    tools_provided: list[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def manifest_path(self) -> Path:
        return self.path / "plugin.toml"


def plugins_dir() -> Path:
    p = paths.DATA_DIR / "plugins"
    p.mkdir(parents=True, exist_ok=True)
    return p


def list_plugins() -> list[PluginInfo]:
    root = plugins_dir()
    out: list[PluginInfo] = []
    for sub in sorted(root.iterdir()):
        if not sub.is_dir() or sub.name.startswith("_") or sub.name.startswith("."):
            continue
        info = PluginInfo(name=sub.name, path=sub)
        manifest = sub / "plugin.toml"
        if manifest.exists():
            try:
                data = tomllib.loads(manifest.read_text())
                info.name = str(data.get("name", sub.name))
                info.version = str(data.get("version", "0.0.0"))
                info.description = str(data.get("description", ""))
                info.author = str(data.get("author", ""))
                info.homepage = str(data.get("homepage", ""))
                info.enabled = bool(data.get("enabled", True))
                tools = data.get("tools", [])
                if isinstance(tools, list):
                    info.tools_provided = [str(t) for t in tools]
            except Exception as e:
                info.error = f"manifest parse: {e}"
        else:
            info.error = "no plugin.toml — add one with name/version/description/enabled"
        out.append(info)
    return out


def set_enabled(plugin_name: str, enabled: bool) -> None:
    target = plugins_dir() / plugin_name
    manifest = target / "plugin.toml"
    if not manifest.exists():
        manifest.write_text(
            f'name = "{plugin_name}"\nversion = "0.0.0"\ndescription = ""\n'
            f'author = ""\nenabled = {"true" if enabled else "false"}\n'
        )
        return
    text = manifest.read_text()
    new_line = f'enabled = {"true" if enabled else "false"}'
    if re.search(r'(?m)^enabled\s*=.*$', text):
        text = re.sub(r'(?m)^enabled\s*=.*$', new_line, text)
    else:
        text = text.rstrip() + "\n" + new_line + "\n"
    manifest.write_text(text)


def install_from_path(src: Path) -> PluginInfo:
    """Copy a directory or .py file from `src` into the plugins dir."""
    import shutil
    src = Path(src).expanduser()
    if not src.exists():
        raise FileNotFoundError(src)
    target_root = plugins_dir()
    if src.is_file() and src.suffix == ".py":
        target = target_root / src.stem
        target.mkdir(exist_ok=True)
        shutil.copy(src, target / "__init__.py")
        manifest = target / "plugin.toml"
        if not manifest.exists():
            manifest.write_text(
                f'name = "{src.stem}"\nversion = "0.0.1"\ndescription = ""\n'
                'author = ""\nenabled = true\n'
            )
    else:
        target = target_root / src.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src, target)
    return PluginInfo(name=target.name, path=target)


def remove(plugin_name: str) -> None:
    import shutil
    target = plugins_dir() / plugin_name
    if target.exists() and target.is_dir():
        shutil.rmtree(target)
