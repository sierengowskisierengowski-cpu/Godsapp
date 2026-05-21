"""Generic per-tool scan view: target + options + live output + findings."""
from __future__ import annotations

import asyncio
import threading
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from godsapp.core import workspaces as ws_svc
from godsapp.core.scans import ScanRequest, runner
from godsapp.tools.base import Tool, ToolOption
from godsapp.ui.header_helpers import open_settings, page_header


class ScanView(Gtk.Box):
    def __init__(self, parent, tool: Tool) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(18); self.set_margin_bottom(18)
        self.set_margin_start(20); self.set_margin_end(20)
        self._parent = parent
        self._tool = tool

        self.append(page_header(
            tool.title or tool.name,
            on_settings=lambda: open_settings(parent),
            subtitle=tool.description or "",
        ))

        # Form
        form = Gtk.ListBox()
        form.set_selection_mode(Gtk.SelectionMode.NONE)
        form.add_css_class("boxed-list")

        self._workspace_dropdown = Gtk.DropDown.new_from_strings([])
        self._workspaces: list = []
        self._reload_workspaces()
        ws_row = Adw.ActionRow(title="Workspace")
        ws_row.add_suffix(self._workspace_dropdown)
        form.append(ws_row)

        self._target_entry = Gtk.Entry()
        self._target_entry.set_placeholder_text("e.g. example.com or 10.0.0.0/24")
        tgt_row = Adw.ActionRow(title="Target")
        tgt_row.add_suffix(self._target_entry)
        form.append(tgt_row)

        self._option_widgets: dict[str, Any] = {}
        for opt in tool.options:
            row = self._build_option_row(opt)
            form.append(row)

        self.append(form)

        # Run button row
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._run_btn = Gtk.Button(label="Run scan")
        self._run_btn.add_css_class("suggested-action")
        self._run_btn.connect("clicked", lambda *_: self._start())
        self._status_lbl = Gtk.Label(label="", xalign=0)
        self._status_lbl.set_hexpand(True)
        self._status_lbl.add_css_class("dim-label")
        btn_row.append(self._run_btn); btn_row.append(self._status_lbl)
        self.append(btn_row)

        # Output
        self._output_buf = Gtk.TextBuffer()
        out_view = Gtk.TextView.new_with_buffer(self._output_buf)
        out_view.set_editable(False); out_view.set_monospace(True)
        out_view.add_css_class("output-pane")
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(220)
        scroll.set_vexpand(True)
        scroll.set_child(out_view)
        self.append(scroll)

        # Findings
        self._findings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        findings_label = Gtk.Label(label="Findings", xalign=0)
        findings_label.add_css_class("section-title")
        self.append(findings_label)
        self.append(self._findings_box)

        self._unsubscribe = runner.subscribe(self._on_event)

    def _reload_workspaces(self) -> None:
        self._workspaces = ws_svc.list_workspaces()
        names = [w.name for w in self._workspaces] or ["(no workspaces — create one first)"]
        model = Gtk.StringList.new(names)
        self._workspace_dropdown.set_model(model)
        self._workspace_dropdown.set_sensitive(bool(self._workspaces))

    def _build_option_row(self, opt: ToolOption) -> Gtk.Widget:
        row = Adw.ActionRow(title=opt.label, subtitle=opt.help or "")
        widget: Gtk.Widget
        if opt.kind == "bool":
            sw = Gtk.Switch(); sw.set_active(bool(opt.default))
            sw.set_valign(Gtk.Align.CENTER)
            widget = sw
            self._option_widgets[opt.key] = ("bool", sw)
        elif opt.kind == "int":
            sb = Gtk.SpinButton.new_with_range(0, 100000, 1)
            sb.set_value(int(opt.default or 0))
            widget = sb
            self._option_widgets[opt.key] = ("int", sb)
        elif opt.kind == "choice" and opt.choices:
            dd = Gtk.DropDown.new_from_strings(opt.choices)
            try:
                idx = opt.choices.index(str(opt.default))
                dd.set_selected(idx)
            except ValueError:
                pass
            widget = dd
            self._option_widgets[opt.key] = ("choice", dd, opt.choices)
        else:
            en = Gtk.Entry()
            if opt.kind == "password":
                en.set_visibility(False)
            if opt.default is not None:
                en.set_text(str(opt.default))
            widget = en
            self._option_widgets[opt.key] = ("text", en)
        row.add_suffix(widget)
        return row

    def _collect_args(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, meta in self._option_widgets.items():
            kind = meta[0]
            if kind == "bool":
                out[key] = meta[1].get_active()
            elif kind == "int":
                out[key] = int(meta[1].get_value())
            elif kind == "choice":
                _, dd, choices = meta
                out[key] = choices[dd.get_selected()]
            else:
                out[key] = meta[1].get_text()
        return out

    def _start(self) -> None:
        self._reload_workspaces()
        if not self._workspaces:
            self._status_lbl.set_text("Create a workspace first (Workspaces in the sidebar).")
            return
        target = self._target_entry.get_text().strip()
        if not target:
            self._status_lbl.set_text("Target is required.")
            return
        ws = self._workspaces[self._workspace_dropdown.get_selected()]
        args = self._collect_args()

        self._output_buf.set_text("")
        self._clear_findings()
        self._status_lbl.set_text("starting…")
        self._run_btn.set_sensitive(False)
        self._current_scan_id: str | None = None

        req = ScanRequest(workspace_id=ws.id, tool=self._tool.name, target=target, args=args)

        def thread_target() -> None:
            try:
                scan = asyncio.run(runner.run(req))
                GLib.idle_add(self._on_complete, scan)
            except Exception as e:
                GLib.idle_add(self._on_error, str(e))

        threading.Thread(target=thread_target, daemon=True).start()

    def _on_event(self, scan_id: str, kind: str, text: str) -> None:
        def apply() -> bool:
            if kind in ("stdout", "stderr"):
                end = self._output_buf.get_end_iter()
                self._output_buf.insert(end, text)
            elif kind == "status":
                self._status_lbl.set_text(text)
            return False
        GLib.idle_add(apply)

    def _on_complete(self, scan) -> bool:
        self._run_btn.set_sensitive(True)
        self._status_lbl.set_text(
            f"{scan.status} · exit {scan.exit_code} · {len(scan.findings)} findings"
        )
        self._render_findings(scan.findings)
        return False

    def _on_error(self, msg: str) -> bool:
        self._run_btn.set_sensitive(True)
        self._status_lbl.set_text(f"error: {msg}")
        return False

    def _clear_findings(self) -> None:
        child = self._findings_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._findings_box.remove(child)
            child = nxt

    def _render_findings(self, findings) -> None:
        self._clear_findings()
        if not findings:
            self._findings_box.append(Gtk.Label(label="No findings.", xalign=0))
            return
        for f in findings:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.add_css_class(f"finding-row")
            row.add_css_class(f"severity-{f.severity}")
            sev = Gtk.Label(label=f.severity.upper())
            sev.add_css_class("severity-badge")
            sev.add_css_class(f"sev-{f.severity}")
            title = Gtk.Label(label=f.title, xalign=0)
            title.set_hexpand(True); title.set_ellipsize(3)
            row.append(sev); row.append(title)
            self._findings_box.append(row)

    def do_unroot(self) -> None:  # type: ignore[override]
        try:
            self._unsubscribe()
        except Exception:
            pass
