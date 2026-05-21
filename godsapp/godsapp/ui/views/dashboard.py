"""Dashboard 2.0 — KPI tiles, severity distribution bars, recent activity feed,
quick-action launchers, system health card. Author: Joseph Sierengowski.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import gi
from sqlalchemy import func, select

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from godsapp import __app_name__
from godsapp.core.health import check_health
from godsapp.db import Evidence, Finding, Scan, Workspace, get_session
from godsapp.tools import registry
from godsapp.ui.header_helpers import open_settings, page_header

_SEV_KEYS = ("critical", "high", "medium", "low", "info")


class DashboardView(Gtk.Box):
    def __init__(self, parent) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.set_margin_top(24); self.set_margin_bottom(24)
        self.set_margin_start(24); self.set_margin_end(24)
        self.add_css_class("dashboard-root")
        self._parent = parent

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True); scroll.set_hexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroll)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(1200)
        scroll.set_child(clamp)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        clamp.set_child(inner)

        # Hero
        inner.append(page_header(
            f"Welcome to {__app_name__}",
            on_settings=lambda: open_settings(parent),
            subtitle="Professional security auditing & research. Press Ctrl+K to jump to anything.",
        ))

        # KPI tiles
        self._tile_workspaces = self._tile("Workspaces", "0", "folder-symbolic", "all projects")
        self._tile_scans      = self._tile("Scans",      "0", "system-run-symbolic", "lifetime")
        self._tile_findings   = self._tile("Findings",   "0", "dialog-warning-symbolic", "across all scans")
        self._tile_evidence   = self._tile("Evidence",   "0", "drive-multidisk-symbolic", "content-addressed")

        grid = Gtk.FlowBox()
        grid.set_max_children_per_line(4); grid.set_min_children_per_line(1)
        grid.set_selection_mode(Gtk.SelectionMode.NONE)
        grid.set_column_spacing(14); grid.set_row_spacing(14)
        grid.set_homogeneous(True)
        for t in (self._tile_workspaces, self._tile_scans,
                  self._tile_findings, self._tile_evidence):
            grid.insert(t, -1)
        inner.append(grid)

        # Two-column row: severity chart  |  system health
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14, homogeneous=True)
        self._sev_body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        row.append(self._card("Severity distribution",
                              "Across every finding in every workspace.",
                              self._sev_body))
        self._status_label = Gtk.Label(xalign=0)
        self._status_label.set_wrap(True)
        self._status_label.add_css_class("status-body")
        row.append(self._card("System status",
                              "Database, REST API, and external tool availability.",
                              self._status_label))
        inner.append(row)

        # Quick actions
        self._actions_body = Gtk.FlowBox()
        self._actions_body.set_max_children_per_line(4); self._actions_body.set_min_children_per_line(1)
        self._actions_body.set_selection_mode(Gtk.SelectionMode.NONE)
        self._actions_body.set_column_spacing(10); self._actions_body.set_row_spacing(10)
        inner.append(self._card("Quick actions",
                                "Jump straight into the most-used tools.",
                                self._actions_body))

        # Recent activity
        self._activity_body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        inner.append(self._card("Recent activity",
                                "Latest 12 scans across all workspaces.",
                                self._activity_body))

        self.refresh()

    # ── tile + card primitives ────────────────────────────────────────────
    def _tile(self, title: str, value: str, icon: str, foot: str) -> Gtk.Widget:
        wrap = Gtk.FlowBoxChild()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.add_css_class("stat-tile")
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        img = Gtk.Image.new_from_icon_name(icon)
        lbl = Gtk.Label(label=title.upper(), xalign=0)
        lbl.add_css_class("stat-title"); lbl.set_hexpand(True)
        head.append(img); head.append(lbl)
        val = Gtk.Label(label=value, xalign=0); val.add_css_class("stat-value")
        foot_lbl = Gtk.Label(label=foot, xalign=0); foot_lbl.add_css_class("stat-delta")
        box.append(head); box.append(val); box.append(foot_lbl)
        wrap.set_child(box)
        wrap._value_label = val  # type: ignore[attr-defined]
        wrap._foot_label = foot_lbl  # type: ignore[attr-defined]
        return wrap

    def _card(self, title: str, subtitle: str, body: Gtk.Widget) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.add_css_class("card")
        head = Gtk.Label(label=title, xalign=0); head.add_css_class("card-title")
        sub = Gtk.Label(label=subtitle, xalign=0); sub.add_css_class("card-sub")
        sub.set_wrap(True)
        box.append(head); box.append(sub); box.append(body)
        return box

    # ── data refresh ──────────────────────────────────────────────────────
    def refresh(self) -> None:
        with get_session() as s:
            wcount = s.execute(select(func.count(Workspace.id))).scalar() or 0
            scount = s.execute(select(func.count(Scan.id))).scalar() or 0
            fcount = s.execute(select(func.count(Finding.id))).scalar() or 0
            ecount = s.execute(select(func.count(Evidence.id))).scalar() or 0

            # severity histogram
            sev_rows = s.execute(
                select(Finding.severity, func.count(Finding.id))
                .group_by(Finding.severity)
            ).all()
            sev_counts = {k: 0 for k in _SEV_KEYS}
            for sev, n in sev_rows:
                if sev in sev_counts:
                    sev_counts[sev] = int(n or 0)

            # scans in last 7 days
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_count = s.execute(
                select(func.count(Scan.id)).where(Scan.created_at >= week_ago)
            ).scalar() or 0

            # recent activity
            activity_rows = s.execute(
                select(Scan, Workspace)
                .join(Workspace, Scan.workspace_id == Workspace.id)
                .order_by(Scan.created_at.desc()).limit(12)
            ).all()
            activity = [{
                "tool": sc.tool, "target": sc.target, "status": sc.status,
                "exit_code": sc.exit_code, "created_at": sc.created_at,
                "workspace": ws.name,
            } for sc, ws in activity_rows]

        self._tile_workspaces._value_label.set_text(str(wcount))   # type: ignore[attr-defined]
        self._tile_scans._value_label.set_text(str(scount))        # type: ignore[attr-defined]
        self._tile_findings._value_label.set_text(str(fcount))     # type: ignore[attr-defined]
        self._tile_evidence._value_label.set_text(str(ecount))     # type: ignore[attr-defined]
        self._tile_scans._foot_label.set_text(                     # type: ignore[attr-defined]
            f"{recent_count} in last 7 days")

        self._render_severity(sev_counts)
        self._render_quick_actions()
        self._render_activity(activity)
        self._render_status()

    def _render_severity(self, counts: dict[str, int]) -> None:
        child = self._sev_body.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling(); self._sev_body.remove(child); child = nxt
        total = max(1, sum(counts.values()))
        for k in _SEV_KEYS:
            self._sev_body.append(self._sev_bar(k, counts.get(k, 0), total))

    def _sev_bar(self, sev: str, count: int, total: int) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add_css_class("sev-bar-wrap")
        lbl = Gtk.Label(label=sev.upper(), xalign=0); lbl.add_css_class("sev-bar-label")
        track = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        track.add_css_class("sev-bar-track"); track.set_hexpand(True)
        fill = Gtk.Box(); fill.add_css_class("sev-bar-fill"); fill.add_css_class(f"sev-{sev}")
        # 0..100 of the track width — use size_request as a hint; HBox without children needs a width
        pct = max(0.0, min(1.0, count / total))
        # Use a horizontal pane via halign + width hint
        fill.set_size_request(int(640 * pct), -1)
        track.append(fill)
        cnt = Gtk.Label(label=str(count), xalign=1); cnt.add_css_class("sev-bar-count")
        row.append(lbl); row.append(track); row.append(cnt)
        return row

    def _render_quick_actions(self) -> None:
        child = self._actions_body.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling(); self._actions_body.remove(child); child = nxt

        # Curated quick-launch tools, falling back to whatever is registered.
        wanted = ["nmap", "ffuf", "nuclei", "subdomain-brute",
                  "sqlmap", "dig", "shodan", "wpscan"]
        chosen = [t for name in wanted if (t := registry.get(name)) is not None]
        if not chosen:
            chosen = registry.all()[:8]

        for tool in chosen[:8]:
            self._actions_body.insert(self._quick_tile(tool), -1)

    def _quick_tile(self, tool) -> Gtk.Widget:
        wrap = Gtk.FlowBoxChild()
        btn = Gtk.Button()
        btn.add_css_class("quick-tile")
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label=tool.title or tool.name, xalign=0)
        title.add_css_class("quick-tile-title")
        sub = Gtk.Label(label=f"{tool.category}  ·  {tool.requires_binary or 'built-in'}",
                        xalign=0); sub.add_css_class("quick-tile-sub")
        sub.set_ellipsize(3)
        body.append(title); body.append(sub)
        btn.set_child(body)
        btn.connect("clicked", lambda *_: self._parent._on_select("tool", tool.name))
        wrap.set_child(btn)
        return wrap

    def _render_activity(self, rows: list[dict]) -> None:
        child = self._activity_body.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling(); self._activity_body.remove(child); child = nxt
        if not rows:
            empty = Gtk.Label(label="No scans yet — pick a tool from the sidebar to start.",
                              xalign=0)
            empty.add_css_class("dim-label")
            self._activity_body.append(empty)
            return
        now = datetime.utcnow()
        for r in rows:
            line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            line.add_css_class("activity-row")
            ts = r["created_at"] or now
            delta = now - ts
            if delta.total_seconds() < 60: when = "just now"
            elif delta.total_seconds() < 3600: when = f"{int(delta.total_seconds() // 60)}m ago"
            elif delta.total_seconds() < 86400: when = f"{int(delta.total_seconds() // 3600)}h ago"
            else: when = f"{int(delta.total_seconds() // 86400)}d ago"
            t = Gtk.Label(label=when, xalign=0); t.add_css_class("activity-time")
            tag = Gtk.Label(label=(r["status"] or "?").upper()); tag.add_css_class("activity-tag")
            msg = Gtk.Label(label=f"{r['tool']}  →  {r['target']}   ({r['workspace']})",
                            xalign=0); msg.add_css_class("activity-msg"); msg.set_hexpand(True)
            msg.set_ellipsize(3)
            line.append(t); line.append(tag); line.append(msg)
            self._activity_body.append(line)

    def _render_status(self) -> None:
        try:
            report = check_health()
            missing = [t for t, ok in report.tools.items() if not ok]
            present = [t for t, ok in report.tools.items() if ok]
            lines = [
                f"●  Database: {'OK' if report.db_ok else 'ERROR'}   {report.db_url}",
                f"●  REST API: {'running' if report.api_running else 'stopped (off by default)'}",
                f"●  Tools available ({len(present)}):  {', '.join(present) or 'none'}",
                f"●  Tools missing  ({len(missing)}):  {', '.join(missing) or 'none'}",
            ]
            self._status_label.set_text("\n".join(lines))
        except Exception as e:
            self._status_label.set_text(f"health check failed: {e}")
