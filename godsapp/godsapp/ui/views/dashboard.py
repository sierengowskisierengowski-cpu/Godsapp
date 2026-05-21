"""Dashboard: summary tiles and recent activity."""
from __future__ import annotations

from sqlalchemy import func, select

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from godsapp import __app_name__
from godsapp.core.health import check_health
from godsapp.db import Evidence, Finding, Scan, Workspace, get_session
from godsapp.ui.header_helpers import open_settings, page_header


class DashboardView(Gtk.Box):
    def __init__(self, parent) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.set_margin_top(24); self.set_margin_bottom(24)
        self.set_margin_start(24); self.set_margin_end(24)
        self.add_css_class("dashboard-root")
        self._parent = parent

        clamp = Adw.Clamp()
        clamp.set_maximum_size(1100)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        clamp.set_child(inner)
        self.append(clamp)

        # Hero with settings cog
        inner.append(page_header(
            f"Welcome to {__app_name__}",
            on_settings=lambda: open_settings(parent),
            subtitle="Professional security auditing & research suite. Pick a tool from the sidebar to start.",
        ))

        # Stat tiles
        self._tile_workspaces = self._tile("Workspaces", "0", "folder-symbolic")
        self._tile_scans = self._tile("Scans", "0", "system-run-symbolic")
        self._tile_findings = self._tile("Findings", "0", "dialog-warning-symbolic")
        self._tile_evidence = self._tile("Evidence", "0", "drive-multidisk-symbolic")

        grid = Gtk.FlowBox()
        grid.set_max_children_per_line(4)
        grid.set_min_children_per_line(1)
        grid.set_selection_mode(Gtk.SelectionMode.NONE)
        grid.set_column_spacing(12); grid.set_row_spacing(12)
        for t in (self._tile_workspaces, self._tile_scans,
                  self._tile_findings, self._tile_evidence):
            grid.insert(t, -1)
        inner.append(grid)

        # System status card
        self._status_label = Gtk.Label(xalign=0)
        self._status_label.set_wrap(True)
        self._status_label.add_css_class("status-body")
        status_card = self._card("System status", self._status_label)
        inner.append(status_card)

        self.refresh()

    def _tile(self, title: str, value: str, icon: str) -> Gtk.Widget:
        wrap = Gtk.FlowBoxChild()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.add_css_class("stat-tile")
        box.set_size_request(220, 96)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        img = Gtk.Image.new_from_icon_name(icon)
        lbl = Gtk.Label(label=title.upper(), xalign=0)
        lbl.add_css_class("stat-title"); lbl.set_hexpand(True)
        head.append(img); head.append(lbl)
        val = Gtk.Label(label=value, xalign=0)
        val.add_css_class("stat-value")
        box.append(head); box.append(val)
        wrap.set_child(box)
        wrap._value_label = val  # type: ignore[attr-defined]
        return wrap

    def _card(self, title: str, body: Gtk.Widget) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.add_css_class("card")
        head = Gtk.Label(label=title, xalign=0)
        head.add_css_class("card-title")
        box.append(head); box.append(body)
        return box

    def refresh(self) -> None:
        with get_session() as s:
            wcount = s.execute(select(func.count(Workspace.id))).scalar() or 0
            scount = s.execute(select(func.count(Scan.id))).scalar() or 0
            fcount = s.execute(select(func.count(Finding.id))).scalar() or 0
            ecount = s.execute(select(func.count(Evidence.id))).scalar() or 0
        self._tile_workspaces._value_label.set_text(str(wcount))  # type: ignore[attr-defined]
        self._tile_scans._value_label.set_text(str(scount))  # type: ignore[attr-defined]
        self._tile_findings._value_label.set_text(str(fcount))  # type: ignore[attr-defined]
        self._tile_evidence._value_label.set_text(str(ecount))  # type: ignore[attr-defined]

        try:
            report = check_health()
            missing = [t for t, ok in report.tools.items() if not ok]
            present = [t for t, ok in report.tools.items() if ok]
            lines = [
                f"Database: {'OK' if report.db_ok else 'ERROR'}  —  {report.db_url}",
                f"REST API: {'running' if report.api_running else 'stopped (off by default)'}",
                f"Tools available ({len(present)}): {', '.join(present) or 'none'}",
                f"Tools missing  ({len(missing)}): {', '.join(missing) or 'none'}",
            ]
            self._status_label.set_text("\n".join(lines))
        except Exception as e:
            self._status_label.set_text(f"health check failed: {e}")
