"""Application settings, persisted to ~/.config/godsapp/settings.toml.

Author: Joseph Sierengowski.

Schema:
    [api]        — REST API server
    [ui]         — theme, accent, scramble toggle, pulse auto-fade
    [database]   — connection URL override
    [threat]     — Shodan / Censys / OTX / AbuseIPDB / MISP credentials
    [reports]    — author, org, defaults
    [terminal]   — embedded VTE terminal
    [scheduler]  — background scheduler
    [evidence]   — evidence locker policies
    [findings]   — findings manager defaults
    [plugins]    — plugin loader policy
    [categories.<cat>] — per-tool-category defaults (timeouts, wordlists, etc.)
"""
from __future__ import annotations

import tomllib
from typing import Any, Optional

from pydantic import BaseModel, Field

from godsapp.core import paths


# ── typed sub-sections ────────────────────────────────────────────────────
class APISettings(BaseModel):
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 7842
    require_token: bool = True


class LoginSettings(BaseModel):
    enabled: bool = True
    user: str = ""           # blank → defaults to $USER on first launch
    salt: str = ""           # hex
    pwhash: str = ""         # sha256 hex of (salt + password)


class UISettings(BaseModel):
    theme: str = "dark"
    accent: str = "cream"
    matrix_scramble: bool = True
    auto_fade_pulse_seconds: int = 6
    show_splash: bool = True
    sounds_enabled: bool = True
    background_storm: bool = True
    # ── storm tuning (v0.4.1 polish pass) ──
    # Volumes are 0–100 ints; audio backend translates to backend-native units.
    storm_strike_volume: int = 35       # sharp electrical crack on a bolt strike
    storm_rumble_volume: int = 18       # ambient rolling rumble between strikes
    # frequency: sparse=60–110s · moderate=15–40s · frequent=6–18s
    storm_frequency: str = "moderate"
    # close/distant intensity variation — when true, ~80% of strikes are
    # distant (small + faint glow) and ~20% are close (large + sharp + flash)
    storm_distance_variation: bool = True
    # preset: whisper=very faint · drizzle=light · standard=default · heavy=loud
    storm_preset: str = "standard"
    # pause the storm renderer + audio while any scan is running so heavy
    # work isn't competing with the visual fx for the GPU
    storm_pause_during_scans: bool = True


class DatabaseSettings(BaseModel):
    url: Optional[str] = None


class ThreatSettings(BaseModel):
    shodan_api_key: str = ""
    censys_id: str = ""
    censys_secret: str = ""
    otx_api_key: str = ""
    abuseipdb_api_key: str = ""
    misp_url: str = ""
    misp_key: str = ""


class ReportsSettings(BaseModel):
    author: str = "Joseph Sierengowski"
    org: str = ""
    watermark: str = ""
    default_format: str = "markdown"
    output_dir: str = ""  # blank → ~/.local/share/godsapp/reports


class ToolPathsSettings(BaseModel):
    """Per-tool detection overrides — when the user has a binary installed
    in a non-standard location, or under an unexpected name, they can pin
    the path here and the detector will trust it."""
    # tool_id → absolute path to the executable
    overrides: dict[str, str] = Field(default_factory=dict)
    # tool_ids the user has explicitly chosen to hide from the missing-tools
    # popover and from the dashboard "Tools missing" counter
    skipped: list[str] = Field(default_factory=list)


class TerminalSettings(BaseModel):
    auto_install_vte: bool = True

    shell: str = ""           # blank → $SHELL or /bin/bash
    font: str = "Monospace 11"
    scrollback_lines: int = 50000
    color_scheme: str = "godsapp"   # godsapp | dracula | solarized | nord | gruvbox
    cursor_blink: bool = True
    show_ascii_header: bool = True
    show_status_line: bool = True
    workspace_logging: bool = True


class SchedulerSettings(BaseModel):
    enabled: bool = True
    max_concurrent: int = 2
    tick_seconds: int = 30


class EvidenceSettings(BaseModel):
    auto_capture: bool = True
    max_size_mb: int = 4096


class FindingsSettings(BaseModel):
    default_status: str = "open"
    severity_threshold: str = "info"   # info | low | medium | high | critical
    custom_tags: str = ""              # comma-separated


class PluginsSettings(BaseModel):
    auto_load: bool = True
    require_signature: bool = False


class OnboardingSettings(BaseModel):
    enabled: bool = True           # show on first launch
    completed: bool = False        # set True after user finishes/skips tour
    show_hints: bool = True        # surface contextual hints in views


class LearnSettings(BaseModel):
    enabled: bool = False          # show Learn panels inside ScanView
    tooltip_delay_ms: int = 800
    show_difficulty_badges: bool = True
    auto_open_for_new_tools: bool = True


class TemplatesSettings(BaseModel):
    default_template: str = "blank"
    confirm_before_apply: bool = True


class UpdatesSettings(BaseModel):
    """In-app updater (GitHub Releases feed)."""
    auto_check: bool = True
    check_interval_hours: int = 24
    include_prereleases: bool = False
    # Skip pkexec / system install and install under ~/.local instead.
    user_scope: bool = False
    # Optional override — point at a self-hosted GitHub-compatible
    # releases JSON feed (e.g. Gitea / a static mirror).
    feed_url: str = ""
    # Persisted by core.updater after every check.
    last_check_at: str = ""
    last_seen_version: str = ""
    # If non-empty, skip notifications for this version (user clicked
    # "Skip this version" on the update toast/dialog).
    skipped_version: str = ""


class DedupSettings(BaseModel):
    """Stored as integer percentages (0–100) so the Settings UI int spin row
    renders the same values the user sees. Callers convert to 0–1 floats."""
    enabled: bool = True
    suggest_threshold: int = 85     # show "looks like a duplicate?" prompt
    auto_merge_threshold: int = 98  # only merge silently above this


class Settings(BaseModel):
    api: APISettings = Field(default_factory=APISettings)
    ui: UISettings = Field(default_factory=UISettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    threat: ThreatSettings = Field(default_factory=ThreatSettings)
    reports: ReportsSettings = Field(default_factory=ReportsSettings)
    terminal: TerminalSettings = Field(default_factory=TerminalSettings)
    login: LoginSettings = Field(default_factory=LoginSettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    evidence: EvidenceSettings = Field(default_factory=EvidenceSettings)
    findings: FindingsSettings = Field(default_factory=FindingsSettings)
    plugins: PluginsSettings = Field(default_factory=PluginsSettings)
    onboarding: OnboardingSettings = Field(default_factory=OnboardingSettings)
    learn: LearnSettings = Field(default_factory=LearnSettings)
    templates: TemplatesSettings = Field(default_factory=TemplatesSettings)
    dedup: DedupSettings = Field(default_factory=DedupSettings)
    tool_paths: ToolPathsSettings = Field(default_factory=ToolPathsSettings)
    updates: UpdatesSettings = Field(default_factory=UpdatesSettings)
    categories: dict[str, dict[str, Any]] = Field(default_factory=dict)


# ── persistence ───────────────────────────────────────────────────────────
def load_settings() -> Settings:
    if not paths.SETTINGS_PATH.exists():
        return Settings()
    try:
        with paths.SETTINGS_PATH.open("rb") as f:
            data = tomllib.load(f)
        return Settings.model_validate(data)
    except Exception:
        return Settings()


def _toml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _emit_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if v is None:
        return '""'
    if isinstance(v, list):
        return "[" + ", ".join(_emit_value(x) for x in v) + "]"
    return f'"{_toml_escape(str(v))}"'


def _emit_section(name: str, values: dict, out: list[str]) -> None:
    scalars = {k: v for k, v in values.items() if not isinstance(v, dict)}
    subsections = {k: v for k, v in values.items() if isinstance(v, dict)}
    out.append(f"[{name}]")
    for k, v in scalars.items():
        out.append(f"{k} = {_emit_value(v)}")
    out.append("")
    for sub_k, sub_v in subsections.items():
        # quote sub-section name if it contains special chars
        sub_name = sub_k if sub_k.isidentifier() else f'"{_toml_escape(sub_k)}"'
        _emit_section(f"{name}.{sub_name}", sub_v, out)


def save_settings(settings: Settings) -> None:
    paths.ensure_directories()
    data = settings.model_dump()
    out: list[str] = [
        "# GodsApp settings — managed by the Settings view.",
        "# Edit carefully; the app re-reads this file on demand.",
        "",
    ]
    for section, values in data.items():
        if isinstance(values, dict):
            _emit_section(section, values, out)
        else:
            out.append(f"{section} = {_emit_value(values)}")
    paths.SETTINGS_PATH.write_text("\n".join(out))


# ── per-category helpers ──────────────────────────────────────────────────
def cat_get(cat: str, key: str, default: Any = None) -> Any:
    s = load_settings()
    return s.categories.get(cat, {}).get(key, default)


def cat_set(cat: str, key: str, value: Any) -> None:
    s = load_settings()
    bucket = s.categories.setdefault(cat, {})
    bucket[key] = value
    save_settings(s)
