"""Tool detection engine.

Resolves a tool_id (e.g. ``"msfvenom"``) to an executable path by:
1. Checking the user's per-tool override path (`settings.tool_paths.overrides`).
2. Walking `$PATH` for every acceptable binary name in the catalog entry.
3. Walking a curated list of standard install locations
   (``/usr/bin``, ``/usr/local/bin``, ``~/.local/bin``, ``~/go/bin``, pipx
   bin dirs) — these catch tools that pacman / pipx / Go drop outside the
   user's interactive `$PATH`.

Detection runs are explicit; no background polling. Callers cache.

Author: Joseph Sierengowski.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from godsapp.core.logging import get_logger
from godsapp.core.tool_catalog import CATALOG, CatalogEntry, get as catalog_get

log = get_logger(__name__)


@dataclass
class Detection:
    tool_id: str
    found: bool
    path: Optional[str] = None     # resolved binary path
    binary: Optional[str] = None   # which of the candidates matched
    via_override: bool = False     # path came from settings override
    via_extra_dir: bool = False    # found outside $PATH (e.g. ~/.local/bin)


def _is_windows() -> bool:
    return platform.system().lower().startswith("win")


def _extra_dirs() -> list[Path]:
    """Standard locations to inspect *in addition* to `$PATH`."""
    home = Path(os.path.expanduser("~"))
    dirs = [
        Path("/usr/bin"), Path("/usr/local/bin"), Path("/usr/sbin"),
        Path("/opt/bin"),
        home / ".local" / "bin",
        home / ".local" / "share" / "pipx" / "venvs",
        home / "go" / "bin",
        Path("/snap/bin"),
        Path("/var/lib/flatpak/exports/bin"),
        home / ".cargo" / "bin",
    ]
    return [d for d in dirs if d.exists()]


def _match_name(haystack: str, needle: str) -> bool:
    if _is_windows():
        return haystack.lower() == needle.lower()
    return haystack == needle


def _which_any(binaries: tuple[str, ...]) -> Optional[tuple[str, str]]:
    """Try each candidate against $PATH using shutil.which. Returns (path, matched_name)."""
    for b in binaries:
        p = shutil.which(b)
        if p:
            return p, b
    return None


def _search_extra(binaries: tuple[str, ...]) -> Optional[tuple[str, str]]:
    """Walk extra dirs (one level only, plus pipx venvs/*/bin)."""
    for d in _extra_dirs():
        # pipx venvs need a one-level descent: ~/.local/share/pipx/venvs/<pkg>/bin/<bin>
        if d.name == "venvs" and d.is_dir():
            for venv in d.iterdir():
                bin_dir = venv / "bin"
                if not bin_dir.is_dir():
                    continue
                for b in binaries:
                    cand = bin_dir / b
                    if cand.is_file() and os.access(cand, os.X_OK):
                        return str(cand), b
            continue
        for b in binaries:
            cand = d / b
            if cand.is_file() and os.access(cand, os.X_OK):
                return str(cand), b
    return None


def detect_one(tool_id: str, *, overrides: Optional[dict[str, str]] = None) -> Detection:
    overrides = overrides or {}
    entry = catalog_get(tool_id)
    if entry is None:
        # Unknown tool — fall back to a single-name lookup.
        p = shutil.which(tool_id)
        return Detection(tool_id, p is not None, p, tool_id if p else None)

    # 1) User override — trust it if the file exists & is executable.
    ov = overrides.get(tool_id, "").strip()
    if ov:
        cand = Path(os.path.expanduser(ov))
        if cand.is_file() and os.access(cand, os.X_OK):
            # Pick the catalog binary whose name matches, otherwise the first.
            matched = next(
                (b for b in entry.binaries if _match_name(cand.name, b)),
                entry.binaries[0],
            )
            return Detection(tool_id, True, str(cand), matched, via_override=True)
        # Override given but broken — still record the failure so the UI can
        # surface a "your override path doesn't work" hint.
        log.warning("tool override for %s does not exist or isn't executable: %s",
                    tool_id, ov)

    # 2) $PATH
    hit = _which_any(entry.binaries)
    if hit:
        path, name = hit
        return Detection(tool_id, True, path, name)

    # 3) Extra dirs
    hit = _search_extra(entry.binaries)
    if hit:
        path, name = hit
        return Detection(tool_id, True, path, name, via_extra_dir=True)

    return Detection(tool_id, False)


def detect_all(*, overrides: Optional[dict[str, str]] = None) -> dict[str, Detection]:
    return {tid: detect_one(tid, overrides=overrides) for tid in CATALOG.keys()}


def test_binary(path: str, timeout: float = 3.0) -> tuple[bool, str]:
    """Run ``<path> --version`` (with --help fallback) and return (ok, first_line)."""
    for arg in ("--version", "-V", "-v", "--help"):
        try:
            proc = subprocess.run(
                [path, arg],
                capture_output=True, text=True, timeout=timeout,
            )
            line = (proc.stdout or proc.stderr or "").strip().splitlines()
            first = line[0] if line else ""
            # 0 / 1 / 2 are all reasonable — many tools exit 1 on --version.
            if proc.returncode in (0, 1, 2) and (first or proc.returncode == 0):
                return True, first or f"exit {proc.returncode}"
        except FileNotFoundError:
            return False, "binary not found"
        except subprocess.TimeoutExpired:
            return False, f"timeout running {arg}"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"
    return False, "no version output"


# ── distro / package-manager detection ─────────────────────────────────
_DISTRO_PKG: dict[str, str] = {
    "arch": "pacman", "manjaro": "pacman", "endeavouros": "pacman",
    "cachyos": "pacman", "garuda": "pacman", "artix": "pacman",
    "debian": "apt", "ubuntu": "apt", "pop": "apt", "mint": "apt",
    "elementary": "apt", "kali": "apt", "parrot": "apt", "raspbian": "apt",
    "fedora": "dnf", "rhel": "dnf", "centos": "dnf", "rocky": "dnf", "almalinux": "dnf",
    "opensuse": "zypper", "opensuse-tumbleweed": "zypper",
    "opensuse-leap": "zypper", "suse": "zypper",
    "void": "xbps",
}


def detect_pkg_manager() -> tuple[str, str]:
    """Return (distro_label, pkg_manager_key). Defaults to ('Linux', 'apt')
    when /etc/os-release is missing or unrecognized; on macOS returns
    ('macOS', 'brew')."""
    if platform.system() == "Darwin":
        return "macOS", "brew"
    try:
        info: dict[str, str] = {}
        with open("/etc/os-release", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    info[k] = v.strip().strip('"')
        name = info.get("PRETTY_NAME") or info.get("NAME") or "Linux"
        ids = (info.get("ID", "") + " " + info.get("ID_LIKE", "")).lower().split()
        for tok in ids:
            if tok in _DISTRO_PKG:
                return name, _DISTRO_PKG[tok]
        return name, "apt"
    except Exception:
        return "Linux", "apt"


def install_cmd_for(entry: CatalogEntry, pkg_mgr: str) -> Optional[str]:
    """Return the install command for the given pkg manager, or fall back
    through a preference chain so we always have *something* to offer."""
    if pkg_mgr in entry.install:
        return entry.install[pkg_mgr]
    for fallback in ("pipx", "pip", "brew", "go"):
        if fallback in entry.install:
            return entry.install[fallback]
    return None
