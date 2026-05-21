"""Primary application window — Adw.ApplicationWindow with sidebar + content."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from godsapp import __app_name__
from godsapp.core.health import check_health
from godsapp.tools import registry
from godsapp.ui.sidebar import Sidebar
from godsapp.ui.views.dashboard import DashboardView
from godsapp.ui.views.evidence import EvidenceView
from godsapp.ui.views.scan_view import ScanView
from godsapp.ui.views.settings import SettingsView
from godsapp.ui.views.workspaces import WorkspacesView


CATEGORY_LABELS: list[tuple[str, str, str]] = [
    # (category-id, title, icon-name)
    ("recon",       "Reconnaissance",       "network-wired-symbolic"),
    ("web",         "Web Application",      "applications-internet-symbolic"),
    ("network",     "Network",              "network-transmit-receive-symbolic"),
    ("password",    "Password & Hash",      "dialog-password-symbolic"),
    ("exploit",     "Exploitation",         "weather-storm-symbolic"),
    ("wireless",    "Wireless",             "network-wireless-symbolic"),
    ("forensics",   "Forensics",            "drive-harddisk-symbolic"),
    ("malware",     "Malware Analysis",     "dialog-warning-symbolic"),
    ("osint",       "OSINT",                "system-search-symbolic"),
    ("crypto",      "Crypto & Encoding",    "channel-secure-symbolic"),
    ("mobile",      "Mobile",               "phone-symbolic"),
    ("cloud",       "Cloud",                "weather-overcast-symbolic"),
]


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title=__app_name__)
        self.set_default_size(1280, 800)
        self.add_css_class("godsapp-window")

        # Header bar
        header = Adw.HeaderBar()
        header.set_title_widget(self._build_title())

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu = Gio.Menu()
        menu.append("About GodsApp", "app.about")
        menu.append("Quit", "app.quit")
        menu_btn.set_menu_model(menu)
        header.pack_end(menu_btn)

        self._health_indicator = Gtk.Label(label="●")
        self._health_indicator.add_css_class("health-dot")
        self._health_indicator.set_tooltip_text("Checking…")
        header.pack_end(self._health_indicator)

        # Sidebar
        self._sidebar = Sidebar(self._on_select)
        self._sidebar.set_size_request(240, -1)

        for cat_id, title, icon in CATEGORY_LABELS:
            tools_in_cat = registry.by_category().get(cat_id, [])
            self._sidebar.add_section(cat_id, title, icon, tools_in_cat)

        self._sidebar.add_pinned("workspaces", "Workspaces", "folder-symbolic")
        self._sidebar.add_pinned("evidence",   "Evidence Locker", "drive-multidisk-symbolic")
        self._sidebar.add_pinned("settings",   "Settings", "preferences-system-symbolic")

        # Content stack
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(140)
        self._stack.set_hexpand(True)
        self._stack.set_vexpand(True)

        self._dashboard = DashboardView(self)
        self._workspaces = WorkspacesView(self)
        self._evidence = EvidenceView(self)
        self._settings_view = SettingsView(self)
        self._stack.add_named(self._dashboard, "dashboard")
        self._stack.add_named(self._workspaces, "workspaces")
        self._stack.add_named(self._evidence, "evidence")
        self._stack.add_named(self._settings_view, "settings")

        self._scan_views: dict[str, ScanView] = {}

        # Split
        split = Adw.NavigationSplitView()
        sidebar_page = Adw.NavigationPage(title="Tools", child=self._sidebar)
        content_page = Adw.NavigationPage(title=__app_name__, child=self._stack)
        split.set_sidebar(sidebar_page)
        split.set_content(content_page)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(split)
        self.set_content(toolbar_view)

        # Health refresh
        self._refresh_health()
        GLib.timeout_add_seconds(15, self._refresh_health)

    def _build_title(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.add_css_class("title-box")
        bolt = Gtk.Label(label="⚡")
        bolt.add_css_class("title-bolt")
        title = Gtk.Label(label=__app_name__)
        title.add_css_class("title-main")
        box.append(bolt)
        box.append(title)
        return box

    def _on_select(self, kind: str, payload: str) -> None:
        if kind == "pinned":
            self._stack.set_visible_child_name(payload)
            return
        if kind == "tool":
            name = payload
            view = self._scan_views.get(name)
            if view is None:
                tool = registry.get(name)
                if tool is None:
                    return
                view = ScanView(self, tool)
                self._scan_views[name] = view
                self._stack.add_named(view, f"tool::{name}")
            self._stack.set_visible_child_name(f"tool::{name}")

    def _refresh_health(self) -> bool:
        try:
            report = check_health()
        except Exception:
            self._health_indicator.set_tooltip_text("health check failed")
            self._health_indicator.remove_css_class("ok")
            self._health_indicator.add_css_class("err")
            return True

        missing = [t for t, ok in report.tools.items() if not ok]
        tip = [
            f"DB: {'OK' if report.db_ok else 'ERROR'}  ({report.db_url})",
            f"API: {'running' if report.api_running else 'stopped'}",
            f"Tools missing: {', '.join(missing) if missing else 'none'}",
        ]
        self._health_indicator.set_tooltip_text("\n".join(tip))
        if report.db_ok and not missing:
            self._health_indicator.remove_css_class("err")
            self._health_indicator.remove_css_class("warn")
            self._health_indicator.add_css_class("ok")
        elif report.db_ok:
            self._health_indicator.remove_css_class("ok")
            self._health_indicator.remove_css_class("err")
            self._health_indicator.add_css_class("warn")
        else:
            self._health_indicator.remove_css_class("ok")
            self._health_indicator.remove_css_class("warn")
            self._health_indicator.add_css_class("err")
        return True
