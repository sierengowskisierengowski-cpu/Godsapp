"""Settings hub — a navigation split-view with one sub-page per concern,
plus an auto-generated sub-page for every registered tool category.

Author: Joseph Sierengowski.
"""
from __future__ import annotations

from typing import Any, Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from godsapp import __version__
from godsapp.core import paths
from godsapp.core.settings import Settings, load_settings, save_settings
from godsapp.tools import registry


# Field spec: (dotted_path, label, kind, default, help)
# kind ∈ text | password | int | bool | choice
SYSTEM_PAGES: list[dict[str, Any]] = [
    {
        "key": "general", "title": "General", "icon": "preferences-system-symbolic",
        "subtitle": "Theme, accent, hover effects, and window animations.",
        "fields": [
            ("ui.theme",                  "Theme",              "choice", "dark",  None,
                ["dark", "light", "system"]),
            ("ui.accent",                 "Accent",             "choice", "cream", None,
                ["cream", "amber", "ivory"]),
            ("ui.matrix_scramble",        "Matrix scramble on hover", "bool", True, None, None),
            ("ui.auto_fade_pulse_seconds","Auto-fade pulse after (sec)", "int", 6,
                "Window-border pulse returns to idle this many seconds after a scan finishes.", None),
            ("ui.show_splash",            "Show splash on launch", "bool", True, None, None),
            ("ui.sounds_enabled",         "Splash sound effects (thunder)", "bool", True,
                "Plays a cinematic thunder rumble during the startup splash. Requires paplay, pw-play, aplay, ffplay, or mpv on the system.", None),
            ("ui.background_storm",       "Live background lightning storm", "bool", True,
                "Random lightning bolts strike across the main window every 15–40 seconds with a faint distant thunder rumble. Turn off for total silence.", None),
            ("database.url",              "Database URL (blank = SQLite)", "text", "", None, None),
        ],
    },
    {
        "key": "api", "title": "REST API", "icon": "network-server-symbolic",
        "subtitle": "Optional local REST server (binds 127.0.0.1).",
        "fields": [
            ("api.enabled",        "Enable API server", "bool", False, None, None),
            ("api.port",           "Port",              "int",  7842, None, None),
            ("api.require_token",  "Require token (~/.config/godsapp/api.token)", "bool", True, None, None),
        ],
    },
    {
        "key": "threat", "title": "Threat Intel", "icon": "system-search-symbolic",
        "subtitle": "API credentials for Shodan, Censys, OTX, AbuseIPDB, MISP.",
        "fields": [
            ("threat.shodan_api_key",    "Shodan API key",      "password", "", None, None),
            ("threat.censys_id",         "Censys API ID",       "text",     "", None, None),
            ("threat.censys_secret",     "Censys API secret",   "password", "", None, None),
            ("threat.otx_api_key",       "AlienVault OTX key (optional)", "password", "", None, None),
            ("threat.abuseipdb_api_key", "AbuseIPDB key",       "password", "", None, None),
            ("threat.misp_url",          "MISP URL",            "text",     "", None, None),
            ("threat.misp_key",          "MISP API key",        "password", "", None, None),
        ],
    },
    {
        "key": "reports", "title": "Reports", "icon": "x-office-document-symbolic",
        "subtitle": "Defaults for the report generator (Markdown, HTML, JSON, SARIF, DOCX, XLSX, PDF).",
        "fields": [
            ("reports.author",         "Author",        "text",   "Joseph Sierengowski", None, None),
            ("reports.org",            "Organisation",  "text",   "", None, None),
            ("reports.watermark",      "Watermark",     "text",   "", None, None),
            ("reports.default_format", "Default format","choice", "markdown", None,
                ["markdown", "html", "json", "sarif", "docx", "xlsx", "pdf"]),
            ("reports.output_dir",     "Output directory (blank = ~/.local/share/godsapp/reports)",
                "text", "", None, None),
        ],
    },
    {
        "key": "scheduler", "title": "Scheduler", "icon": "alarm-symbolic",
        "subtitle": "Background cron-style runner.",
        "fields": [
            ("scheduler.enabled",        "Scheduler enabled",       "bool", True, None, None),
            ("scheduler.tick_seconds",   "Tick interval (sec)",     "int",  30,   None, None),
            ("scheduler.max_concurrent", "Max concurrent jobs",     "int",  2,    None, None),
        ],
    },
    {
        "key": "terminal", "title": "Terminal", "icon": "utilities-terminal-symbolic",
        "subtitle": "Embedded VTE terminal preferences.",
        "fields": [
            ("terminal.shell",            "Shell (blank = $SHELL)", "text", "", None, None),
            ("terminal.font",             "Font",                   "text", "Monospace 11", None, None),
            ("terminal.scrollback_lines", "Scrollback lines",       "int",  10000, None, None),
        ],
    },
    {
        "key": "evidence", "title": "Evidence", "icon": "drive-multidisk-symbolic",
        "subtitle": "Evidence locker policies.",
        "fields": [
            ("evidence.auto_capture", "Auto-capture scan output", "bool", True, None, None),
            ("evidence.max_size_mb",  "Per-file size cap (MB)",   "int",  4096, None, None),
        ],
    },
    {
        "key": "findings", "title": "Findings Manager", "icon": "dialog-warning-symbolic",
        "subtitle": "Defaults for the Findings Manager.",
        "fields": [
            ("findings.default_status",      "Default status",      "choice",
                "open", None, ["open", "triaged", "confirmed", "fixed", "wontfix", "duplicate"]),
            ("findings.severity_threshold",  "Show ≥ severity",     "choice",
                "info", None, ["info", "low", "medium", "high", "critical"]),
            ("findings.custom_tags",         "Custom tags (comma)", "text",   "", None, None),
        ],
    },
    {
        "key": "plugins", "title": "Plugins", "icon": "application-x-addon-symbolic",
        "subtitle": "Plugin loader policy.",
        "fields": [
            ("plugins.auto_load",         "Auto-load on startup",        "bool", True,  None, None),
            ("plugins.require_signature", "Require manifest signature",  "bool", False, None, None),
        ],
    },
]


CATEGORY_ICONS = {
    "recon":     "network-wired-symbolic",
    "web":       "applications-internet-symbolic",
    "network":   "network-transmit-receive-symbolic",
    "password":  "dialog-password-symbolic",
    "exploit":   "weather-storm-symbolic",
    "wireless":  "network-wireless-symbolic",
    "forensics": "drive-harddisk-symbolic",
    "malware":   "dialog-warning-symbolic",
    "osint":     "system-search-symbolic",
    "crypto":    "channel-secure-symbolic",
    "mobile":    "phone-symbolic",
    "cloud":     "weather-overcast-symbolic",
    "vuln":      "security-high-symbolic",
    "threat":    "network-server-symbolic",
}


def _get_dotted(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
        if cur is None:
            return None
    return cur


def _set_dotted(settings: Settings, path: str, value: Any) -> None:
    parts = path.split(".")
    section = parts[0]
    bucket = getattr(settings, section)
    obj = bucket
    for p in parts[1:-1]:
        if isinstance(obj, dict):
            obj = obj.setdefault(p, {})
        else:
            obj = getattr(obj, p)
    leaf = parts[-1]
    if isinstance(obj, dict):
        obj[leaf] = value
    else:
        try:
            setattr(obj, leaf, value)
        except Exception:
            pass


class SettingsView(Gtk.Box):
    """Hub layout: left sidebar lists pages, right pane shows the selected one."""

    def __init__(self, parent) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._parent = parent
        self._settings: Settings = load_settings()
        self._unsaved_widgets: dict[str, tuple] = {}
        # _unsaved_widgets[(page_key, field_path)] = (kind, widget [, choices])

        # ── left: page index ────────────────────────────────────────────
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(120)
        self._stack.set_hexpand(True)
        self._stack.set_vexpand(True)

        sidebar = Gtk.StackSidebar()
        sidebar.set_stack(self._stack)
        sidebar.set_size_request(220, -1)
        sidebar.add_css_class("settings-sidebar")
        self.append(sidebar)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.append(sep)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        right.set_hexpand(True); right.set_vexpand(True)
        right.append(self._stack)
        self.append(right)

        # ── pages ────────────────────────────────────────────────────────
        for spec in SYSTEM_PAGES:
            page = self._build_form_page(spec["key"], spec["title"],
                                         spec["subtitle"], spec["fields"])
            self._stack.add_titled(page, spec["key"], spec["title"])

        # Per-tool-category sub-pages: build from the live registry.
        for cat, tools in registry.by_category().items():
            page = self._build_category_page(cat, tools)
            self._stack.add_titled(page, f"cat:{cat}", cat.title())

        # About
        about_page = self._build_about_page()
        self._stack.add_titled(about_page, "about", "About")

    # ── navigation ────────────────────────────────────────────────────────
    def goto(self, anchor: str) -> None:
        names = [c for c in self._stack.get_pages()] if False else None
        # Just attempt; Gtk.Stack is silent on unknown name.
        try:
            self._stack.set_visible_child_name(anchor)
        except Exception:
            pass

    # ── page builders ─────────────────────────────────────────────────────
    def _build_form_page(self, key: str, title: str, subtitle: str,
                         fields: list[tuple]) -> Gtk.Widget:
        outer = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title=title, description=subtitle)
        outer.add(group)

        for spec in fields:
            path, label, kind, default, help_text, choices = (
                spec + (None,) * (6 - len(spec)))[:6]
            current = _get_dotted(self._settings, path)
            if current is None:
                current = default
            row, packed = self._make_row(label, kind, current, choices, help_text)
            self._unsaved_widgets[(key, path)] = packed
            group.add(row)

        save_btn = Gtk.Button(label="Save settings")
        save_btn.add_css_class("suggested-action")
        save_btn.set_halign(Gtk.Align.START)
        save_btn.connect("clicked", lambda *_: self._save())
        status_lbl = Gtk.Label(label="", xalign=0)
        status_lbl.add_css_class("dim-label")
        self._status_lbl = status_lbl
        save_row = Adw.ActionRow()
        save_row.add_prefix(save_btn)
        save_row.add_suffix(status_lbl)
        save_group = Adw.PreferencesGroup()
        save_group.add(save_row)
        outer.add(save_group)
        return outer

    def _build_category_page(self, cat: str, tools: list) -> Gtk.Widget:
        outer = Adw.PreferencesPage()
        # Tool inventory group
        inv = Adw.PreferencesGroup(
            title=f"{cat.title()} tools",
            description=f"{len(tools)} registered. Binary availability is checked at launch.",
        )
        import shutil
        for tool in tools:
            sub = (f"binary: {tool.requires_binary}" if tool.requires_binary
                   else "pure-python — no system binary required")
            row = Adw.ActionRow(title=tool.title or tool.name, subtitle=sub)
            status = "—"
            if tool.requires_binary:
                status = "✓ installed" if shutil.which(tool.requires_binary) else "✗ missing"
            badge = Gtk.Label(label=status)
            badge.add_css_class("dim-label" if "—" in status or "✓" in status else "warning")
            row.add_suffix(badge)
            inv.add(row)
        outer.add(inv)

        # Per-category defaults group (free-form key/value, stored under categories.<cat>)
        cat_settings = self._settings.categories.get(cat, {})
        # Provide a handful of commonly-useful keys with sensible defaults.
        defaults = [
            ("default_timeout_sec", "Default subprocess timeout (sec)", "int", cat_settings.get("default_timeout_sec", 600)),
            ("default_wordlist",    "Default wordlist path",            "text", cat_settings.get("default_wordlist", "")),
            ("notes",               "Notes / reminders for this category", "text", cat_settings.get("notes", "")),
        ]
        defaults_group = Adw.PreferencesGroup(
            title=f"{cat.title()} defaults",
            description="These values are surfaced to every tool in this category.",
        )
        for key, label, kind, current in defaults:
            row, packed = self._make_row(label, kind, current, None, None)
            self._unsaved_widgets[(f"cat:{cat}", f"categories.{cat}.{key}")] = packed
            defaults_group.add(row)
        outer.add(defaults_group)

        # Save button
        save_group = Adw.PreferencesGroup()
        btn = Gtk.Button(label="Save settings")
        btn.add_css_class("suggested-action"); btn.set_halign(Gtk.Align.START)
        btn.connect("clicked", lambda *_: self._save())
        save_group.add(btn)
        outer.add(save_group)
        return outer

    def _build_about_page(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        g = Adw.PreferencesGroup(title="GodsApp", description="Security auditing and research suite.")
        for label, value in [
            ("Version", __version__),
            ("Author",  "Joseph Sierengowski"),
            ("App ID",  "com.sierengowski.GodsApp"),
            ("Config",  str(paths.CONFIG_DIR)),
            ("Data",    str(paths.DATA_DIR)),
            ("Settings file", str(paths.SETTINGS_PATH)),
        ]:
            row = Adw.ActionRow(title=label, subtitle=value)
            g.add(row)
        page.add(g)
        return page

    # ── row factory ───────────────────────────────────────────────────────
    def _make_row(self, label: str, kind: str, current: Any,
                  choices: list | None, help_text: str | None) -> tuple[Gtk.Widget, tuple]:
        if kind == "bool":
            row = Adw.SwitchRow(title=label, subtitle=help_text or "")
            row.set_active(bool(current))
            return row, ("bool", row)
        if kind == "int":
            row = Adw.SpinRow.new_with_range(0, 1_000_000, 1)
            row.set_title(label)
            if help_text:
                row.set_subtitle(help_text)
            try:
                row.set_value(int(current or 0))
            except (TypeError, ValueError):
                row.set_value(0)
            return row, ("int", row)
        if kind == "choice" and choices:
            model = Gtk.StringList.new(choices)
            row = Adw.ComboRow(title=label, subtitle=help_text or "")
            row.set_model(model)
            try:
                idx = choices.index(str(current))
            except ValueError:
                idx = 0
            row.set_selected(idx)
            return row, ("choice", row, choices)
        # text / password
        row = Adw.EntryRow(title=label)
        if kind == "password":
            try:
                row.set_show_apply_button(False)
            except Exception:
                pass
            # Adw.EntryRow itself is plain-text; for passwords we add a PasswordEntry suffix
            # Adw < 1.5 doesn't have Adw.PasswordEntryRow, so fall back to set_text.
            row.set_text(str(current or ""))
            return row, ("text", row)
        row.set_text(str(current or ""))
        return row, ("text", row)

    # ── persistence ───────────────────────────────────────────────────────
    def _save(self) -> None:
        s = self._settings
        for (page_key, path), packed in self._unsaved_widgets.items():
            kind = packed[0]
            try:
                if kind == "bool":
                    val = packed[1].get_active()
                elif kind == "int":
                    val = int(packed[1].get_value())
                elif kind == "choice":
                    choices = packed[2]
                    idx = packed[1].get_selected()
                    val = choices[idx] if 0 <= idx < len(choices) else choices[0]
                else:
                    val = packed[1].get_text()
            except Exception:
                continue
            _set_dotted(s, path, val)
        try:
            save_settings(s)
            self._status_lbl.set_text("saved")
            GLib.timeout_add_seconds(3, lambda: (self._status_lbl.set_text(""), False)[1])
            # Surface a toast through the main window if available
            parent_toaster = getattr(self._parent, "_toast_overlay", None)
            if parent_toaster is not None:
                parent_toaster.add_toast(Adw.Toast(title="Settings saved"))
        except Exception as e:
            self._status_lbl.set_text(f"save failed: {e}")
