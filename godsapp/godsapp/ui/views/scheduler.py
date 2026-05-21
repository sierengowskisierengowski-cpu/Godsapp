"""Scheduler view — CRUD on `Schedule` rows; the background loop ticks every
`scheduler.tick_seconds` and fires due jobs through `ScanRunner`."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402
from sqlalchemy import select

from godsapp.core import workspaces as ws_svc
from godsapp.core.scheduler import parse_cron, scheduler
from godsapp.db import Schedule, get_session
from godsapp.tools import registry
from godsapp.ui.header_helpers import open_settings, page_header


class SchedulerView(Gtk.Box):
    def __init__(self, parent) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(20); self.set_margin_bottom(20)
        self.set_margin_start(20); self.set_margin_end(20)
        self._parent = parent

        new_btn = Gtk.Button(label="New schedule")
        new_btn.add_css_class("suggested-action")
        new_btn.connect("clicked", lambda *_: self._open_new_dialog())
        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.add_css_class("flat")
        refresh_btn.connect("clicked", lambda *_: self.refresh())

        self.append(page_header(
            "Scheduler",
            on_settings=lambda: open_settings(parent, "scheduler"),
            trailing=[refresh_btn, new_btn],
            subtitle="Cron-style background scans. Tick interval and concurrency live in Settings → Scheduler.",
        ))

        self._status_lbl = Gtk.Label(label="", xalign=0)
        self._status_lbl.add_css_class("dim-label")
        self.append(self._status_lbl)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list.add_css_class("boxed-list")
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True); scroll.set_child(self._list)
        self.append(scroll)

        self.refresh()

    # ── data ──────────────────────────────────────────────────────────────
    def refresh(self) -> None:
        child = self._list.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._list.remove(child)
            child = nxt
        with get_session() as s:
            rows = s.execute(select(Schedule).order_by(Schedule.created_at.desc())).scalars().all()
            data = [{
                "id": r.id, "tool": r.tool, "target": r.target, "cron": r.cron,
                "enabled": r.enabled, "last_run_at": r.last_run_at,
                "next_run_at": r.next_run_at, "workspace_id": r.workspace_id,
            } for r in rows]
        if not data:
            self._list.append(Adw.ActionRow(
                title="No schedules yet.",
                subtitle="Click ‘New schedule’ to add one."))
            self._status_lbl.set_text("scheduler running" if scheduler._thread and scheduler._thread.is_alive() else "scheduler stopped")
            return
        ws_lookup = {w.id: w.name for w in ws_svc.list_workspaces()}
        for d in data:
            row = Adw.ActionRow(
                title=f"{d['tool']} → {d['target']}",
                subtitle=(f"workspace: {ws_lookup.get(d['workspace_id'],'?')}  ·  cron: {d['cron']}  "
                          f"·  next: {d['next_run_at'].isoformat() if d['next_run_at'] else '—'}  "
                          f"·  last: {d['last_run_at'].isoformat() if d['last_run_at'] else 'never'}"),
            )
            sw = Gtk.Switch(); sw.set_active(d["enabled"])
            sw.set_valign(Gtk.Align.CENTER)
            sw.connect("notify::active",
                       lambda s, _p, sid=d["id"]: self._toggle(sid, s.get_active()))
            del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
            del_btn.add_css_class("flat")
            del_btn.connect("clicked", lambda _b, sid=d["id"]: self._delete(sid))
            row.add_suffix(sw); row.add_suffix(del_btn)
            self._list.append(row)
        self._status_lbl.set_text(
            f"{len(data)} schedule(s)  ·  scheduler {'running' if scheduler._thread and scheduler._thread.is_alive() else 'stopped'}"
        )

    def _toggle(self, sid: str, enabled: bool) -> None:
        from datetime import datetime
        with get_session() as s:
            r = s.get(Schedule, sid)
            if r is None: return
            r.enabled = enabled
            if enabled and not r.next_run_at:
                try:
                    r.next_run_at = parse_cron(r.cron, datetime.utcnow())
                except Exception:
                    pass

    def _delete(self, sid: str) -> None:
        with get_session() as s:
            r = s.get(Schedule, sid)
            if r is not None:
                s.delete(r)
        self.refresh()

    # ── new-schedule dialog ───────────────────────────────────────────────
    def _open_new_dialog(self) -> None:
        ws_list = ws_svc.list_workspaces()
        if not ws_list:
            self._status_lbl.set_text("Create a workspace first.")
            return
        tools = registry.all()
        if not tools:
            self._status_lbl.set_text("No tools registered.")
            return

        dlg = Adw.Window(transient_for=self._parent, modal=True)
        dlg.set_title("New schedule")
        dlg.set_default_size(540, 420)
        tv = Adw.ToolbarView()
        hb = Adw.HeaderBar()
        cancel = Gtk.Button(label="Cancel"); cancel.connect("clicked", lambda *_: dlg.close())
        save = Gtk.Button(label="Create"); save.add_css_class("suggested-action")
        hb.pack_start(cancel); hb.pack_end(save)
        tv.add_top_bar(hb)
        page = Adw.PreferencesPage()
        g = Adw.PreferencesGroup(title="Schedule")

        ws_dd = Adw.ComboRow(title="Workspace")
        ws_dd.set_model(Gtk.StringList.new([w.name for w in ws_list]))
        g.add(ws_dd)

        tool_dd = Adw.ComboRow(title="Tool")
        tool_dd.set_model(Gtk.StringList.new([f"{t.category}/{t.name}" for t in tools]))
        g.add(tool_dd)

        target_row = Adw.EntryRow(title="Target")
        g.add(target_row)
        cron_row = Adw.EntryRow(title="Cron (m h dom mon dow)")
        cron_row.set_text("0 * * * *")
        g.add(cron_row)
        args_row = Adw.EntryRow(title="Extra args (key=value, comma-separated)")
        g.add(args_row)

        page.add(g)
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True); scroll.set_child(page)
        tv.set_content(scroll)
        dlg.set_content(tv)

        def do_save(*_a) -> None:
            from datetime import datetime
            ws = ws_list[ws_dd.get_selected()]
            tool = tools[tool_dd.get_selected()]
            target = target_row.get_text().strip()
            cron = cron_row.get_text().strip() or "0 * * * *"
            if not target:
                return
            args: dict = {}
            for chunk in (args_row.get_text() or "").split(","):
                if "=" in chunk:
                    k, v = chunk.split("=", 1)
                    args[k.strip()] = v.strip()
            try:
                next_at = parse_cron(cron, datetime.utcnow())
            except Exception:
                next_at = None
            with get_session() as s:
                s.add(Schedule(
                    workspace_id=ws.id, tool=tool.name, target=target,
                    args=args, cron=cron, enabled=True, next_run_at=next_at,
                ))
            dlg.close()
            self.refresh()

        save.connect("clicked", do_save)
        dlg.present()
