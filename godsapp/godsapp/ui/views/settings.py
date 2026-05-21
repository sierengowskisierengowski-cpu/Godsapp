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
from godsapp.core.tool_catalog import CATALOG
from godsapp.core.tool_detect import detect_all, detect_one, test_binary
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
                "Random lightning bolts strike across the main window. Tune the storm with the controls below.", None),
            ("ui.storm_preset",           "Storm preset", "choice", "standard",
                "Whisper = barely-there atmosphere · Drizzle = light · Standard = balanced · Heavy = full thunderstorm.",
                ["whisper", "drizzle", "standard", "heavy"]),
            ("ui.storm_frequency",        "Strike frequency", "choice", "moderate",
                "How often a strike fires. Sparse ≈ every 60–110s · Moderate ≈ 15–40s · Frequent ≈ 6–18s.",
                ["sparse", "moderate", "frequent"]),
            ("ui.storm_strike_volume",    "Strike volume (0–100)", "int", 35,
                "Volume of the sharp electrical crack when a bolt strikes.", None),
            ("ui.storm_rumble_volume",    "Rumble volume (0–100)", "int", 18,
                "Volume of the deep rolling thunder that fades out after each strike.", None),
            ("ui.storm_distance_variation", "Vary strike distance (close vs distant)", "bool", True,
                "About 80% of strikes are distant (small + faint + soft rumble) and 20% are close (large + sharp + full-screen flash) for a more atmospheric feel.", None),
            ("ui.storm_pause_during_scans", "Auto-pause storm during active scans", "bool", True,
                "Suppress visual lightning + audio while any scan is running so the GPU is free for the work.", None),
            ("terminal.auto_install_vte", "Offer one-click VTE install", "bool", True,
                "When the embedded terminal can't find libvte, show an Install button (uses pkexec) instead of just copy-paste instructions.", None),
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
        "key": "updates", "title": "Updates", "icon": "software-update-available-symbolic",
        "subtitle": "Check GitHub Releases for newer GodsApp versions.",
        "fields": [
            ("updates.auto_check",           "Check for updates automatically",
                "bool", True, None, None),
            ("updates.check_interval_hours", "Check interval (hours)",
                "int",  24, (1, 720), None),
            ("updates.include_prereleases",  "Include pre-releases (alpha/beta/rc)",
                "bool", False, None, None),
            ("updates.user_scope",           "Install to ~/.local (skip pkexec)",
                "bool", False, None, None),
            ("updates.feed_url",             "Custom releases feed URL (optional)",
                "text", "", None, None),
            ("updates.last_check_at",        "Last checked (read-only)",
                "text", "", None, None),
            ("updates.last_seen_version",    "Last seen version (read-only)",
                "text", "", None, None),
            ("updates.skipped_version",      "Skipped version (clear to re-prompt)",
                "text", "", None, None),
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
    {
        "key": "onboarding", "title": "Onboarding", "icon": "help-faq-symbolic",
        "subtitle": "First-launch guided tour through every major surface.",
        "fields": [
            ("onboarding.enabled",    "Show tour on first launch", "bool", True, None, None),
            ("onboarding.completed",  "Tour completed (uncheck to re-run on next launch)",
                "bool", False, None, None),
            ("onboarding.show_hints", "Surface contextual hints in views",
                "bool", True, None, None),
        ],
    },
    {
        "key": "learn", "title": "Learn Mode", "icon": "accessories-dictionary-symbolic",
        "subtitle": "Inline tutorials, per-tool difficulty badges, expanded tooltips.",
        "fields": [
            ("learn.enabled",                "Show Learn panels inside every tool",
                "bool", False, None, None),
            ("learn.show_difficulty_badges", "Show difficulty dots in the sidebar",
                "bool", True, None, None),
            ("learn.auto_open_for_new_tools", "Auto-open Learn panel for tools you haven't used",
                "bool", True, None, None),
            ("learn.tooltip_delay_ms",       "Tooltip delay (ms)",
                "int", 800, None, None),
        ],
    },
    {
        "key": "templates", "title": "Workspace Templates", "icon": "view-list-symbolic",
        "subtitle": "Pre-configured engagement starters (Bug Bounty, Pentest, CTF, Forensics…).",
        "fields": [
            ("templates.default_template",     "Default template",
                "choice", "blank", None,
                ["blank", "bug-bounty", "ext-pentest", "int-pentest", "red-team",
                 "threat-hunt", "forensics", "ctf", "compliance", "home-lab"]),
            ("templates.confirm_before_apply", "Confirm before applying template",
                "bool", True, None, None),
        ],
    },
    {
        "key": "dedup", "title": "Findings Dedup", "icon": "edit-copy-symbolic",
        "subtitle": "Detect and merge duplicate findings; chain related findings.",
        "fields": [
            ("dedup.enabled",              "Suggest merges for likely duplicates",
                "bool", True, None, None),
            ("dedup.suggest_threshold",    "Suggestion threshold (0–100)",
                "int", 85, "Findings scoring above this percent similarity prompt a merge.", None),
            ("dedup.auto_merge_threshold", "Silent-merge threshold (0–100)",
                "int", 98, "Findings scoring above this percent merge automatically with no prompt.", None),
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

        # Tool Paths: dedicated sub-page (custom rendering — not a simple
        # field form). Lets the user pin per-tool override paths, test
        # them, and run a one-click "re-detect everything" sweep.
        self._stack.add_titled(self._build_tool_paths_page(), "tool_paths", "Tool Paths")

        # Per-tool-category sub-pages: build from the live registry.
        for cat, tools in registry.by_category().items():
            page = self._build_category_page(cat, tools)
            self._stack.add_titled(page, f"cat:{cat}", cat.title())

        # About
        about_page = self._build_about_page()
        self._stack.add_titled(about_page, "about", "About")

    # ── tool paths page ───────────────────────────────────────────────────
    def _build_tool_paths_page(self) -> Gtk.Widget:
        outer = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(
            title="Tool Paths",
            description=("Per-tool detection overrides. Useful when a binary "
                         "lives in a non-standard location (Snap, Flatpak, "
                         "a custom prefix) or has been installed under an "
                         "unexpected name."),
        )
        outer.add(group)

        # Re-detect everything button
        actions = Gtk.Box(spacing=8)
        redetect = Gtk.Button(label="Re-detect all tools")
        redetect.add_css_class("suggested-action")
        redetect.connect("clicked", lambda *_: self._refresh_tool_path_rows())
        actions.append(redetect)
        open_missing = Gtk.Button(label="Open Missing Tools dialog…")
        open_missing.connect("clicked", lambda *_: self._open_missing_dialog())
        actions.append(open_missing)
        actions_row = Adw.ActionRow()
        actions_row.add_prefix(actions)
        group.add(actions_row)

        # One ActionRow per cataloged tool, with the resolved path and a
        # "Set…" / "Test" / "Clear" trio.
        self._tool_path_rows: dict[str, Adw.ActionRow] = {}
        self._tool_path_status: dict[str, Gtk.Label] = {}
        for tid in sorted(CATALOG.keys()):
            entry = CATALOG[tid]
            row = Adw.ActionRow(title=entry.title,
                                subtitle=f"{tid}  ·  {entry.category}")
            status = Gtk.Label(xalign=1); status.add_css_class("dim-label")
            status.set_xalign(1); status.set_hexpand(False)
            status.set_max_width_chars(60); status.set_ellipsize(3)
            row.add_suffix(status)

            set_btn = Gtk.Button.new_from_icon_name("document-open-symbolic")
            set_btn.set_tooltip_text("Pick binary…")
            set_btn.add_css_class("flat")
            set_btn.connect("clicked", lambda _b, t=tid: self._pick_override(t))
            row.add_suffix(set_btn)

            test_btn = Gtk.Button.new_from_icon_name("emblem-ok-symbolic")
            test_btn.set_tooltip_text("Test binary")
            test_btn.add_css_class("flat")
            test_btn.connect("clicked", lambda _b, t=tid: self._test_tool(t))
            row.add_suffix(test_btn)

            clear_btn = Gtk.Button.new_from_icon_name("edit-clear-symbolic")
            clear_btn.set_tooltip_text("Clear override")
            clear_btn.add_css_class("flat")
            clear_btn.connect("clicked", lambda _b, t=tid: self._clear_override(t))
            row.add_suffix(clear_btn)

            group.add(row)
            self._tool_path_rows[tid] = row
            self._tool_path_status[tid] = status

        self._refresh_tool_path_rows()
        return outer

    def _refresh_tool_path_rows(self) -> None:
        s = load_settings()
        self._settings = s
        dets = detect_all(overrides=dict(s.tool_paths.overrides))
        for tid, status in self._tool_path_status.items():
            d = dets.get(tid)
            if d is None:
                status.set_text("?")
                continue
            if d.found:
                tag = "override" if d.via_override else ("extra-dir" if d.via_extra_dir else "PATH")
                status.set_text(f"✓ {d.path}  [{tag}]")
            else:
                ov = s.tool_paths.overrides.get(tid, "")
                status.set_text(f"✗ missing" + (f"  (override: {ov})" if ov else ""))

    def _pick_override(self, tool_id: str) -> None:
        entry = CATALOG.get(tool_id)
        if entry is None:
            return
        dialog = Gtk.FileDialog()
        dialog.set_title(f"Locate {entry.title} binary")
        win = self.get_root()
        parent_win = win if isinstance(win, Gtk.Window) else None
        def _cb(d, res):
            try:
                f = d.open_finish(res)
            except Exception:
                return
            if f is None:
                return
            path = f.get_path()
            if not path:
                return
            s = load_settings()
            s.tool_paths.overrides[tool_id] = path
            save_settings(s)
            self._refresh_tool_path_rows()
        dialog.open(parent_win, None, _cb)

    def _clear_override(self, tool_id: str) -> None:
        s = load_settings()
        if tool_id in s.tool_paths.overrides:
            del s.tool_paths.overrides[tool_id]
            save_settings(s)
        self._refresh_tool_path_rows()

    def _test_tool(self, tool_id: str) -> None:
        s = load_settings()
        d = detect_one(tool_id, overrides=dict(s.tool_paths.overrides))
        if not d.found or not d.path:
            self._tool_path_status[tool_id].set_text("✗ not detected — set an override first")
            return
        ok, line = test_binary(d.path)
        prefix = "✓" if ok else "✗"
        self._tool_path_status[tool_id].set_text(f"{prefix} {d.path}  →  {line[:120]}")

    def _open_missing_dialog(self) -> None:
        from godsapp.ui.missing_tools_dialog import MissingToolsDialog
        win = self.get_root()
        dlg = MissingToolsDialog(win if isinstance(win, Gtk.Window) else None)
        dlg.connect("close-request",
                    lambda *_: (self._refresh_tool_path_rows(), False)[1])
        dlg.present()

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
