"""Primary application window — Adw.ApplicationWindow with sidebar, content
stack, header search trigger, command palette (Ctrl+K), and a bottom status bar.

Author: Joseph Sierengowski.
"""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from godsapp import __app_name__, __version__
from godsapp.core.health import check_health
from godsapp.core.scans import runner
from godsapp.core.settings import load_settings
from godsapp.tools import registry
from godsapp.ui.command_palette import CommandPalette, build_commands
from godsapp.ui.onboarding import OnboardingWindow, maybe_show_tour
from godsapp.ui.sidebar import Sidebar
from godsapp.ui.storm import LightningOverlay
from godsapp.ui.terminal_overlay import TerminalOverlay
from godsapp.ui.views.api_console import ApiConsoleView
from godsapp.ui.views.dashboard import DashboardView
from godsapp.ui.views.evidence import EvidenceView
from godsapp.ui.views.findings import FindingsView
from godsapp.ui.views.plugins import PluginsView
from godsapp.ui.views.replay import ReplayView
from godsapp.ui.views.reports import ReportsView
from godsapp.ui.views.scan_view import ScanView
from godsapp.ui.views.scheduler import SchedulerView
from godsapp.ui.views.settings import SettingsView
from godsapp.ui.views.workspaces import WorkspacesView


CATEGORY_LABELS: list[tuple[str, str, str]] = [
    ("recon",       "Reconnaissance",         "network-wired-symbolic"),
    ("web",         "Web Application",        "applications-internet-symbolic"),
    ("vuln",        "Vulnerability Scanner",  "security-high-symbolic"),
    ("network",     "Network",                "network-transmit-receive-symbolic"),
    ("password",    "Password & Hash",        "dialog-password-symbolic"),
    ("exploit",     "Exploitation",           "weather-storm-symbolic"),
    ("wireless",    "Wireless",               "network-wireless-symbolic"),
    ("forensics",   "Forensics",              "drive-harddisk-symbolic"),
    ("malware",     "Malware Analysis",       "dialog-warning-symbolic"),
    ("osint",       "OSINT",                  "system-search-symbolic"),
    ("threat",      "Threat Intelligence",    "network-server-symbolic"),
    ("crypto",      "Crypto & Encoding",      "channel-secure-symbolic"),
    ("mobile",      "Mobile",                 "phone-symbolic"),
    ("cloud",       "Cloud",                  "weather-overcast-symbolic"),
]

_STATE_CLASSES = ("state-idle", "state-running", "state-ok", "state-err")

PINNED_ITEMS: list[tuple[str, str, str]] = [
    ("dashboard",  "Dashboard",       "view-dashboard-symbolic"),
    ("workspaces", "Workspaces",      "folder-symbolic"),
    ("findings",   "Findings",        "dialog-warning-symbolic"),
    ("evidence",   "Evidence Locker", "drive-multidisk-symbolic"),
    ("reports",    "Reports",         "x-office-document-symbolic"),
    ("scheduler",  "Scheduler",       "alarm-symbolic"),
    ("replay",     "Replay Engine",   "media-playback-start-symbolic"),
    ("plugins",    "Plugins",         "application-x-addon-symbolic"),
    ("api",        "API Console",     "network-server-symbolic"),
    ("settings",   "Settings",        "preferences-system-symbolic"),
]


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title=__app_name__)
        self.set_default_size(1380, 860)
        self.add_css_class("godsapp-window")
        self._set_state("idle")
        self._auto_fade_source: int | None = None
        self._status_text_default = "ready"

        # ── header bar ────────────────────────────────────────────────────
        header = Adw.HeaderBar()
        header.set_title_widget(self._build_title())

        self._search_trigger = self._build_search_trigger()
        header.pack_start(self._search_trigger)

        # Always-visible terminal toggle button — lightning + console glyph.
        # Lives in the header so users can summon/dismiss the embedded shell
        # at any time without remembering the double-click shortcut.
        self._terminal_btn = self._build_terminal_toggle()
        header.pack_start(self._terminal_btn)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu = Gio.Menu()
        menu.append("Command palette  (Ctrl+K)", "app.palette")
        menu.append("Refresh current view  (F5)", "app.refresh")
        menu.append("About GodsApp", "app.about")
        menu.append("Quit", "app.quit")
        menu_btn.set_menu_model(menu)
        header.pack_end(menu_btn)

        self._health_indicator = Gtk.Label(label="●")
        self._health_indicator.add_css_class("health-dot")
        self._health_indicator.set_tooltip_text("Checking…")
        header.pack_end(self._health_indicator)

        # ── sidebar (live search built-in) ────────────────────────────────
        self._sidebar = Sidebar(self._on_select)
        self._sidebar.set_size_request(280, -1)

        for key, title, icon in PINNED_ITEMS:
            self._sidebar.add_pinned(key, title, icon)
        for cat_id, title, icon in CATEGORY_LABELS:
            tools_in_cat = registry.by_category().get(cat_id, [])
            self._sidebar.add_section(cat_id, title, icon, tools_in_cat)

        # ── content stack ────────────────────────────────────────────────
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(140)
        self._stack.set_hexpand(True); self._stack.set_vexpand(True)

        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(self._stack)

        # Views
        self._dashboard = DashboardView(self)
        self._workspaces = WorkspacesView(self)
        self._findings_view = FindingsView(self)
        self._evidence = EvidenceView(self)
        self._reports_view = ReportsView(self)
        self._scheduler_view = SchedulerView(self)
        self._replay_view = ReplayView(self)
        self._plugins_view = PluginsView(self)
        self._api_view = ApiConsoleView(self)
        self._settings_view = SettingsView(self)

        self._stack.add_named(self._dashboard,       "dashboard")
        self._stack.add_named(self._workspaces,      "workspaces")
        self._stack.add_named(self._findings_view,   "findings")
        self._stack.add_named(self._evidence,        "evidence")
        self._stack.add_named(self._reports_view,    "reports")
        self._stack.add_named(self._scheduler_view,  "scheduler")
        self._stack.add_named(self._replay_view,     "replay")
        self._stack.add_named(self._plugins_view,    "plugins")
        self._stack.add_named(self._api_view,        "api")
        self._stack.add_named(self._settings_view,   "settings")

        self._scan_views: dict[str, ScanView] = {}

        # ── split + status bar ────────────────────────────────────────────
        # The terminal overlay slides down INSIDE the content pane (below the
        # header, to the right of the sidebar), so it occupies the full
        # workspace area and resizes with the window automatically. Pinned
        # ASCII header + status line sit at the top of the overlay; the VTE
        # flexes to fill the rest.
        self._content_overlay = Gtk.Overlay()
        self._content_overlay.set_child(self._toast_overlay)
        self._terminal_overlay = TerminalOverlay(self)
        self._content_overlay.add_overlay(self._terminal_overlay)

        split = Adw.NavigationSplitView()
        sidebar_page = Adw.NavigationPage(title="Tools", child=self._sidebar)
        content_page = Adw.NavigationPage(title=__app_name__, child=self._content_overlay)
        split.set_sidebar(sidebar_page)
        split.set_content(content_page)

        self._status_bar = self._build_status_bar()

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        body.set_vexpand(True); body.set_hexpand(True)
        body.append(split)
        body.append(self._status_bar)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(body)

        # Live background lightning storm — transparent click-through layer
        # behind the entire UI. Terminal overlay was already attached inside
        # the content pane above so it correctly sits below the header and
        # to the right of the sidebar.
        root_overlay = Gtk.Overlay()
        self._storm = LightningOverlay()
        root_overlay.set_child(self._storm)
        toolbar_view.set_hexpand(True); toolbar_view.set_vexpand(True)
        root_overlay.add_overlay(toolbar_view)
        self.set_content(root_overlay)

        # Health refresh
        self._refresh_health()
        GLib.timeout_add_seconds(15, self._refresh_health)

        # Subscribe to scan runner so the window border + status bar reflect scan state
        self._scan_unsub = runner.subscribe(self._on_scan_event)
        self.connect("close-request", self._on_close)

        # Keyboard shortcuts (controller scope = entire window)
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key)
        self.add_controller(key_ctrl)

        # Explicit window-scoped shortcut for Ctrl+K so the palette opens even
        # when an entry/textview has focus (app accelerators don't always reach
        # widgets that consume key events first).
        try:
            sc_ctrl = Gtk.ShortcutController()
            sc_ctrl.set_scope(Gtk.ShortcutScope.GLOBAL)
            sc_ctrl.add_shortcut(Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("<Primary>k"),
                Gtk.CallbackAction.new(lambda *_a: (self.open_command_palette(), True)[1]),
            ))
            sc_ctrl.add_shortcut(Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("F5"),
                Gtk.CallbackAction.new(lambda *_a: (self.refresh_current(), True)[1]),
            ))
            self.add_controller(sc_ctrl)
        except Exception:
            pass

    # ── public helpers ────────────────────────────────────────────────────
    def show_toast(self, message: str) -> None:
        try:
            self._toast_overlay.add_toast(Adw.Toast(title=message))
        except Exception:
            pass

    def open_command_palette(self) -> None:
        # Guard against double-fire (Ctrl+K is bound via both app accel and a
        # window ShortcutController — if both fire we'd stack two palettes).
        existing = getattr(self, "_palette_open", None)
        if existing is not None:
            try:
                existing.present()
                return
            except Exception:
                self._palette_open = None
        # Use the cached static commands (pages + tools + settings + slashes)
        # so palette opens instantly even on slow disks; DB-backed sources
        # (workspaces + findings) are appended lazily off the main thread.
        # Always hand the palette a *fresh copy* — extend_commands() mutates
        # the list, and we must not pollute the static cache across openings.
        cmds = list(self._palette_static_cache())
        palette = CommandPalette(self, cmds, on_pick=self._on_palette_pick)
        self._palette_open = palette
        palette.connect("close-request", lambda *_: (setattr(self, "_palette_open", None), False)[1])
        palette.present()
        # Lazy DB fetch — runs in a worker thread, results pushed back on idle.
        import threading
        def _bg() -> None:
            try:
                from godsapp.ui.command_palette import (
                    _build_dynamic_commands,
                )
                dyn = _build_dynamic_commands()
            except Exception:
                dyn = []
            def _apply() -> bool:
                if palette is self._palette_open and dyn:
                    try: palette.extend_commands(dyn)
                    except Exception: pass
                return False
            GLib.idle_add(_apply)
        threading.Thread(target=_bg, daemon=True, name="palette-dyn").start()

    def _palette_static_cache(self) -> list:
        cache = getattr(self, "_palette_static", None)
        if cache is None:
            cache = build_commands(PINNED_ITEMS, CATEGORY_LABELS,
                                   include_dynamic=False)
            self._palette_static = cache
        return cache

    def refresh_current(self) -> None:
        name = self._stack.get_visible_child_name() or "dashboard"
        if name.startswith("tool::"):
            self._set_status_text(f"refreshed {name}")
            return
        self._on_select("pinned", name)

    def _set_status_text(self, text: str) -> None:
        self._sb_value.set_text(text or self._status_text_default)

    # ── internals ─────────────────────────────────────────────────────────
    def _build_title(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.add_css_class("title-box")
        box.add_css_class("title-box-clickable")
        box.set_tooltip_text("Double-click to summon the terminal")
        # Double-click anywhere on the title → toggle terminal overlay
        click = Gtk.GestureClick.new()
        click.set_button(1)
        def _on_click(gesture, n_press, x, y):
            if n_press == 2:
                try:
                    self._terminal_overlay.toggle()
                except Exception:
                    log.exception("terminal toggle failed")
        click.connect("pressed", _on_click)
        box.add_controller(click)
        try:
            from importlib.resources import files
            svg_path = files("godsapp.resources.icons").joinpath("godsapp-logo.svg")
            img = Gtk.Image.new_from_file(str(svg_path))
            img.set_pixel_size(28)
            img.add_css_class("logo-image"); img.add_css_class("bolt-logo")
            logo: Gtk.Widget = img
        except Exception:
            lbl = Gtk.Label(label="☁⚡")
            lbl.add_css_class("title-bolt"); lbl.add_css_class("bolt-logo")
            logo = lbl
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title = Gtk.Label(label=__app_name__.upper()); title.add_css_class("title-main")
        sub = Gtk.Label(label=f"OLYMPUS · v{__version__}"); sub.add_css_class("title-sub")
        text.append(title); text.append(sub)
        box.append(logo); box.append(text)
        return box

    def _build_terminal_toggle(self) -> Gtk.Widget:
        btn = Gtk.ToggleButton()
        btn.add_css_class("header-terminal-btn")
        btn.add_css_class("flat")
        btn.set_tooltip_text("Toggle embedded terminal  (or double-click the title)")
        inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        bolt = Gtk.Label(label="⚡"); bolt.add_css_class("term-btn-bolt")
        icon = Gtk.Image.new_from_icon_name("utilities-terminal-symbolic")
        inner.append(bolt); inner.append(icon)
        btn.set_child(inner)
        # Use 'toggled' so the button's pressed state tracks the actual
        # terminal visibility (e.g. when toggled via title double-click).
        self._terminal_btn_handler = None
        def _on_toggled(b):
            try:
                if b.get_active() and not self._terminal_overlay.get_reveal_child():
                    self._terminal_overlay.show_terminal()
                elif not b.get_active() and self._terminal_overlay.get_reveal_child():
                    self._terminal_overlay.hide_terminal()
            except Exception:
                pass
        self._terminal_btn_handler = btn.connect("toggled", _on_toggled)
        return btn

    def _sync_terminal_btn(self, visible: bool) -> None:
        """Keep the header toggle button state in sync with the overlay."""
        try:
            if self._terminal_btn.get_active() != visible:
                # Block our own handler so we don't recurse into show/hide.
                self._terminal_btn.handler_block(self._terminal_btn_handler)
                self._terminal_btn.set_active(visible)
                self._terminal_btn.handler_unblock(self._terminal_btn_handler)
        except Exception:
            pass

    def _build_search_trigger(self) -> Gtk.Widget:
        btn = Gtk.Button()
        btn.add_css_class("header-search-btn")
        inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Image.new_from_icon_name("system-search-symbolic")
        lbl = Gtk.Label(label="Jump to anything…", xalign=0)
        lbl.set_hexpand(True)
        kbd = Gtk.Label(label="Ctrl+K"); kbd.add_css_class("header-search-kbd")
        inner.append(icon); inner.append(lbl); inner.append(kbd)
        btn.set_child(inner)
        btn.connect("clicked", lambda *_: self.open_command_palette())
        return btn

    def _build_status_bar(self) -> Gtk.Widget:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bar.add_css_class("status-bar")
        def kv(key: str, value: str) -> tuple[Gtk.Label, Gtk.Label]:
            k = Gtk.Label(label=key); k.add_css_class("sb-key")
            v = Gtk.Label(label=value); v.add_css_class("sb-value")
            return k, v
        sep = lambda: Gtk.Label(label="·")  # noqa: E731

        # Left: status / message
        sk, self._sb_value = kv("STATUS", self._status_text_default)
        bar.append(sk); bar.append(self._sb_value)
        bar.append(sep())

        # Middle: tools count
        tk, self._sb_tools = kv("TOOLS", str(len(registry.all())))
        bar.append(tk); bar.append(self._sb_tools)
        bar.append(sep())

        # DB
        dk, self._sb_db = kv("DB", "checking…")
        bar.append(dk); bar.append(self._sb_db)
        bar.append(sep())

        # API
        ak, self._sb_api = kv("API", "stopped")
        bar.append(ak); bar.append(self._sb_api)

        # Right-aligned: shortcut hint + version
        spacer = Gtk.Box(); spacer.set_hexpand(True)
        bar.append(spacer)

        hk = Gtk.Label(label="Ctrl+K  palette   ·   F5  refresh   ·   Ctrl+,  settings   ·   Esc  dashboard")
        hk.add_css_class("sb-key")
        bar.append(hk)
        return bar

    def _set_state(self, state: str) -> None:
        cls = f"state-{state}"
        for s in _STATE_CLASSES:
            if s != cls:
                self.remove_css_class(s)
        self.add_css_class(cls)

    def _on_scan_event(self, _scan_id: str, kind: str, text: str) -> None:
        def apply() -> bool:
            if kind == "status":
                t = (text or "").lower()
                if "start" in t or "running" in t:
                    self._set_state("running"); self._cancel_auto_fade()
                    self._set_status_text("scan running…")
                    try: self._storm.pause_for_scan()
                    except Exception: pass
                elif "complete" in t or "ok" in t or "success" in t or "exit 0" in t:
                    self._set_state("ok"); self._schedule_auto_fade()
                    self._set_status_text("scan complete")
                    try: self._storm.resume_after_scan()
                    except Exception: pass
                elif "fail" in t or "error" in t:
                    self._set_state("err"); self._schedule_auto_fade(critical=True)
                    self._set_status_text(f"scan failed: {text}")
                    try: self._storm.resume_after_scan()
                    except Exception: pass
            elif kind in ("stdout", "stderr"):
                # Visual state only — DO NOT inc/dec the storm pause counter
                # here; pairing is owned exclusively by status start/complete
                # events so the counter can't drift if stdout arrives before
                # or after the status event.
                if "state-running" not in self.get_css_classes():
                    self._set_state("running"); self._cancel_auto_fade()
            return False
        GLib.idle_add(apply)

    def _cancel_auto_fade(self) -> None:
        if self._auto_fade_source is not None:
            try:
                GLib.source_remove(self._auto_fade_source)
            except Exception:
                pass
            self._auto_fade_source = None

    def _schedule_auto_fade(self, *, critical: bool = False) -> None:
        self._cancel_auto_fade()
        try:
            seconds = max(2, int(load_settings().ui.auto_fade_pulse_seconds))
        except Exception:
            seconds = 6
        if critical:
            seconds = max(seconds, 12)

        def _fade() -> bool:
            self._set_state("idle")
            self._auto_fade_source = None
            return False

        self._auto_fade_source = GLib.timeout_add_seconds(seconds, _fade)

    def _on_close(self, *_a) -> bool:
        try: self._scan_unsub()
        except Exception: pass
        self._cancel_auto_fade()
        try:
            from godsapp.core.scheduler import scheduler
            scheduler.stop()
        except Exception:
            pass
        return False

    def _on_palette_pick(self, kind: str, key: str) -> None:
        if kind == "page":
            self._on_select("pinned", key)
        elif kind == "tool":
            self._on_select("tool", key)
        elif kind == "settings":
            self._on_select("pinned", "settings")
            sv = self._settings_view
            if hasattr(sv, "goto"):
                try: sv.goto(key)
                except Exception: pass
        elif kind == "workspace":
            # Jump to the Workspaces page (deep-link to a specific workspace
            # editor is a v0.4.1 enhancement; for now, just surface the page).
            self._on_select("pinned", "workspaces")
            self.show_toast(f"Workspace: {key[:8]}…")
        elif kind == "finding":
            self._on_select("pinned", "findings")
            # Defer the editor open until the FindingsView has refreshed.
            try:
                fv = self._findings_view
                GLib.idle_add(lambda: (fv._open_edit(key), False)[1])
            except Exception:
                pass
        elif kind == "slash":
            self._handle_slash(key)

    def _handle_slash(self, slash: str) -> None:
        if slash == "/tour":
            self.show_onboarding(force=True); return
        if slash == "/learn":
            try:
                from godsapp.core.settings import load_settings, save_settings
                s = load_settings()
                s.learn.enabled = not s.learn.enabled
                save_settings(s)
                self.show_toast(
                    f"Learn Mode {'enabled' if s.learn.enabled else 'disabled'}")
            except Exception:
                self.show_toast("Could not toggle Learn Mode")
            return
        if slash == "/terminal":
            try: self._terminal_overlay.toggle()
            except Exception: self.show_toast("Terminal failed to open")
            return
        if slash == "/refresh":
            self.refresh_current(); return
        if slash == "/dashboard":
            self._on_select("pinned", "dashboard"); return
        if slash == "/help":
            self.show_toast(
                "Slash: /tour /learn /terminal /refresh /dashboard  ·  "
                "Tags: #critical #high #beginner #expert  ·  Ctrl+K palette")
            return

    def show_onboarding(self, *, force: bool = False) -> None:
        # Singleton guard — if a tour is already open, present it instead
        # of stacking a second window (would otherwise both write
        # onboarding.completed on close).
        existing = getattr(self, "_onboarding_win", None)
        if existing is not None:
            try:
                if existing.get_visible():
                    existing.present(); return
            except Exception:
                pass
            self._onboarding_win = None
        try:
            win = maybe_show_tour(self, on_jump=self._on_tour_jump, force=force)
            if win is not None:
                self._onboarding_win = win
                win.connect(
                    "close-request",
                    lambda *_: (setattr(self, "_onboarding_win", None), False)[1],
                )
        except Exception:
            pass

    def _on_tour_jump(self, target: str) -> None:
        if target == "palette":
            self.open_command_palette(); return
        if target == "focus-sidebar":
            try: self._sidebar.focus_search()
            except Exception: pass
            return
        if target in ("workspaces", "findings", "evidence", "dashboard",
                      "reports", "settings"):
            self._on_select("pinned", target)

    def _on_key(self, _ctrl, keyval, _kc, state) -> bool:
        # Ctrl+K and F5 are app-level accelerators (see application.py); do not
        # bind them here too or they double-fire on some compositors.
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and keyval in (Gdk.KEY_comma,):
            self._on_select("pinned", "settings"); return True
        if ctrl and keyval in (Gdk.KEY_f, Gdk.KEY_F):
            self._sidebar.focus_search(); return True
        if keyval == Gdk.KEY_Escape:
            self._on_select("pinned", "dashboard"); return True
        # Ctrl+1..9 jump to pinned items
        if ctrl and Gdk.KEY_1 <= keyval <= Gdk.KEY_9:
            idx = keyval - Gdk.KEY_1
            if 0 <= idx < len(PINNED_ITEMS):
                self._on_select("pinned", PINNED_ITEMS[idx][0])
                return True
        return False

    def _on_select(self, kind: str, payload: str) -> None:
        if kind == "pinned":
            self._stack.set_visible_child_name(payload)
            self._set_status_text(payload)
            handler = {
                "dashboard":  getattr(self._dashboard,        "refresh", None),
                "workspaces": getattr(self._workspaces,       "refresh", None),
                "findings":   getattr(self._findings_view,    "refresh", None),
                "evidence":   getattr(self._evidence,         "refresh", None),
                "reports":    getattr(self._reports_view,     "_refresh_past", None),
                "scheduler":  getattr(self._scheduler_view,   "refresh", None),
                "replay":     getattr(self._replay_view,      "refresh", None),
                "plugins":    getattr(self._plugins_view,     "refresh", None),
            }.get(payload)
            if callable(handler):
                try: handler()
                except Exception: pass
            return
        if kind == "tool":
            name = payload
            view = self._scan_views.get(name)
            if view is None:
                tool = registry.get(name)
                if tool is None:
                    self.show_toast(f"Tool '{name}' is not registered.")
                    return
                view = ScanView(self, tool)
                self._scan_views[name] = view
                self._stack.add_named(view, f"tool::{name}")
            self._stack.set_visible_child_name(f"tool::{name}")
            self._set_status_text(f"tool · {name}")

    def _refresh_health(self) -> bool:
        try:
            report = check_health()
        except Exception:
            self._health_indicator.set_tooltip_text("health check failed")
            self._health_indicator.remove_css_class("ok")
            self._health_indicator.add_css_class("err")
            self._sb_db.set_text("error")
            return True
        missing = [t for t, ok in report.tools.items() if not ok]
        tip = [
            f"DB: {'OK' if report.db_ok else 'ERROR'}  ({report.db_url})",
            f"API: {'running' if report.api_running else 'stopped'}",
            f"Tools missing: {', '.join(missing) if missing else 'none'}",
        ]
        self._health_indicator.set_tooltip_text("\n".join(tip))
        if report.db_ok and not missing:
            self._health_indicator.remove_css_class("err"); self._health_indicator.remove_css_class("warn")
            self._health_indicator.add_css_class("ok")
        elif report.db_ok:
            self._health_indicator.remove_css_class("ok"); self._health_indicator.remove_css_class("err")
            self._health_indicator.add_css_class("warn")
        else:
            self._health_indicator.remove_css_class("ok"); self._health_indicator.remove_css_class("warn")
            self._health_indicator.add_css_class("err")

        self._sb_db.set_text("ok" if report.db_ok else "error")
        self._sb_api.set_text("running" if report.api_running else "stopped")
        self._sb_tools.set_text(f"{len(report.tools) - len(missing)}/{len(report.tools)} available")
        return True
