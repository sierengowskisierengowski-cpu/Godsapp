"""Replay engine — list past scans, replay a scan with the same parameters,
or replay with modifications via the relevant scan view."""
from __future__ import annotations

import asyncio
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402
from sqlalchemy import select

from godsapp.core.scans import ScanRequest, runner
from godsapp.db import Scan, Workspace, get_session
from godsapp.tools import registry
from godsapp.ui.header_helpers import open_settings, page_header


class ReplayView(Gtk.Box):
    def __init__(self, parent) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(20); self.set_margin_bottom(20)
        self.set_margin_start(20); self.set_margin_end(20)
        self._parent = parent

        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.add_css_class("flat")
        refresh_btn.connect("clicked", lambda *_: self.refresh())

        self.append(page_header(
            "Replay Engine",
            on_settings=lambda: open_settings(parent),
            trailing=[refresh_btn],
            subtitle="Re-run any previous scan with the same parameters, or open it in its scan view to modify and re-run.",
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

    def refresh(self) -> None:
        child = self._list.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._list.remove(child)
            child = nxt
        with get_session() as s:
            rows = s.execute(
                select(Scan, Workspace)
                .join(Workspace, Scan.workspace_id == Workspace.id)
                .order_by(Scan.created_at.desc()).limit(100)
            ).all()
            data = [{
                "id": sc.id, "tool": sc.tool, "category": sc.category,
                "target": sc.target, "args": dict(sc.args or {}),
                "status": sc.status, "exit_code": sc.exit_code,
                "created_at": sc.created_at, "finished_at": sc.finished_at,
                "workspace_id": ws.id, "workspace_name": ws.name,
            } for sc, ws in rows]
        if not data:
            self._list.append(Adw.ActionRow(
                title="No scans recorded yet.",
                subtitle="Run a scan from the sidebar to populate the replay log."))
            return
        for d in data:
            stamp = d['created_at'].isoformat() if d['created_at'] else '—'
            row = Adw.ActionRow(
                title=f"{d['tool']} → {d['target']}",
                subtitle=(f"{d['workspace_name']}  ·  {d['category']}  ·  "
                          f"{d['status']} (exit {d['exit_code']})  ·  {stamp}"),
            )
            replay_btn = Gtk.Button(label="Replay")
            replay_btn.add_css_class("flat")
            replay_btn.connect("clicked", lambda _b, x=d: self._replay(x))
            modify_btn = Gtk.Button(label="Replay with edits…")
            modify_btn.add_css_class("flat")
            modify_btn.connect("clicked", lambda _b, x=d: self._open_in_scan_view(x))
            row.add_suffix(modify_btn); row.add_suffix(replay_btn)
            self._list.append(row)

    def _replay(self, d: dict) -> None:
        if registry.get(d["tool"]) is None:
            self._status_lbl.set_text(f"tool '{d['tool']}' no longer registered")
            return
        req = ScanRequest(workspace_id=d["workspace_id"], tool=d["tool"],
                          target=d["target"], args=d["args"])
        self._status_lbl.set_text(f"replaying {d['tool']} → {d['target']} …")

        def thread_body() -> None:
            try:
                scan = asyncio.run(runner.run(req))
                GLib.idle_add(
                    self._on_done, scan.status, scan.exit_code, len(scan.findings)
                )
            except Exception as e:
                GLib.idle_add(self._on_done, "error", -1, 0, str(e))

        threading.Thread(target=thread_body, daemon=True).start()

    def _on_done(self, status: str, exit_code: int, n_findings: int, err: str = "") -> bool:
        msg = (f"{status}  ·  exit {exit_code}  ·  {n_findings} findings"
               if not err else f"error: {err}")
        self._status_lbl.set_text(msg)
        self.refresh()
        toaster = getattr(self._parent, "_toast_overlay", None)
        if toaster is not None:
            toaster.add_toast(Adw.Toast(title=f"Replay: {msg}"))
        return False

    def _open_in_scan_view(self, d: dict) -> None:
        # Hand off to the relevant scan view, pre-populating target/args.
        if registry.get(d["tool"]) is None:
            self._status_lbl.set_text(f"tool '{d['tool']}' no longer registered")
            return
        try:
            self._parent._on_select("tool", d["tool"])
            sv = self._parent._scan_views.get(d["tool"])
            if sv is not None:
                sv._target_entry.set_text(d["target"])
                for key, value in (d["args"] or {}).items():
                    meta = sv._option_widgets.get(key)
                    if not meta: continue
                    kind = meta[0]
                    try:
                        if kind == "bool":
                            meta[1].set_active(bool(value))
                        elif kind == "int":
                            meta[1].set_value(int(value))
                        elif kind == "choice":
                            choices = meta[2]
                            if str(value) in choices:
                                meta[1].set_selected(choices.index(str(value)))
                        else:
                            meta[1].set_text(str(value))
                    except Exception:
                        continue
        except Exception:
            pass
