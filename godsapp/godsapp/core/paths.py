"""XDG-compliant directory layout for GodsApp.

Layout (matches Meli pattern):
    ~/.config/godsapp/                  — settings, api token, plugins.toml
    ~/.local/share/godsapp/             — DB, evidence, workspaces, logs, cache
        godsapp.db
        evidence/                       — raw artifacts (hash-named)
        workspaces/                     — per-workspace working trees
        logs/                           — rotating logs
        cache/                          — transient tool caches
        plugins/                        — user-installed plugins

The install.sh creates every directory upfront (Meli lesson) so first-launch
never hits a missing-directory error.
"""
from __future__ import annotations

from pathlib import Path

from platformdirs import PlatformDirs

_DIRS = PlatformDirs(appname="godsapp", appauthor=False, ensure_exists=False)

CONFIG_DIR: Path = Path(_DIRS.user_config_dir)
DATA_DIR: Path = Path(_DIRS.user_data_dir)
CACHE_DIR: Path = Path(_DIRS.user_cache_dir)
STATE_DIR: Path = Path(_DIRS.user_state_dir)

LOG_DIR: Path = DATA_DIR / "logs"
EVIDENCE_DIR: Path = DATA_DIR / "evidence"
WORKSPACE_DIR: Path = DATA_DIR / "workspaces"
PLUGIN_DIR: Path = DATA_DIR / "plugins"
DB_PATH: Path = DATA_DIR / "godsapp.db"

SETTINGS_PATH: Path = CONFIG_DIR / "settings.toml"
API_TOKEN_PATH: Path = CONFIG_DIR / "api.token"


def ensure_directories() -> None:
    """Create every required directory. Safe to call repeatedly."""
    for d in (CONFIG_DIR, DATA_DIR, CACHE_DIR, STATE_DIR,
              LOG_DIR, EVIDENCE_DIR, WORKSPACE_DIR, PLUGIN_DIR):
        d.mkdir(parents=True, exist_ok=True)
