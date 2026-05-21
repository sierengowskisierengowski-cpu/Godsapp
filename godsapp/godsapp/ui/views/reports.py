"""Reports view — pick a workspace + format, generate, and reveal the output."""
from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gio, Gtk  # noqa: E402

from godsapp.core import reports as rep_svc
from godsapp.core import workspaces as ws_svc
from godsapp.core.settings import load_settings
from godsapp.ui.header_helpers import open_settings, page_header


class ReportsView(Gtk.Box):
    def __init__(self, parent) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(20); self.set_margin_bottom(20)
        self.set_margin_start(20); self.set_margin_end(20)
        self._parent = parent

        self.append(page_header(
            "Reports",
            on_settings=lambda: open_settings(parent, "reports"),
            subtitle="Generate Markdown, HTML, JSON, SARIF, DOCX, XLSX, or PDF reports per workspace.",
        ))

        form = Gtk.ListBox()
        form.set_selection_mode(Gtk.SelectionMode.NONE)
        form.add_css_class("boxed-list")

        # Workspace
        self._workspaces = ws_svc.list_workspaces()
        ws_names = [w.name for w in self._workspaces] or ["(no workspaces — create one first)"]
        self._ws_dd = Gtk.DropDown.new_from_strings(ws_names)
        self._ws_dd.set_sensitive(bool(self._workspaces))
        wsrow = Adw.ActionRow(title="Workspace")
        wsrow.add_suffix(self._ws_dd); form.append(wsrow)

        # Format
        self._fmt_dd = Gtk.DropDown.new_from_strings(rep_svc.SUPPORTED_FORMATS)
        try:
            self._fmt_dd.set_selected(rep_svc.SUPPORTED_FORMATS.index(
                load_settings().reports.default_format))
        except (ValueError, AttributeError):
            self._fmt_dd.set_selected(0)
        fmtrow = Adw.ActionRow(
            title="Format",
            subtitle="DOCX/XLSX/PDF require the optional libraries. MD/HTML/JSON/SARIF always work.",
        )
        fmtrow.add_suffix(self._fmt_dd); form.append(fmtrow)

        # Output dir override
        self._out_entry = Gtk.Entry()
        self._out_entry.set_placeholder_text("(leave blank for default output dir)")
        self._out_entry.set_hexpand(True)
        outrow = Adw.ActionRow(title="Output path (optional)")
        outrow.add_suffix(self._out_entry); form.append(outrow)

        self.append(form)

        # Actions
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        gen_btn = Gtk.Button(label="Generate report")
        gen_btn.add_css_class("suggested-action")
        gen_btn.connect("clicked", lambda *_: self._generate())
        self._status_lbl = Gtk.Label(label="", xalign=0)
        self._status_lbl.set_hexpand(True); self._status_lbl.set_wrap(True)
        self._status_lbl.add_css_class("dim-label")
        actions.append(gen_btn); actions.append(self._status_lbl)
        self.append(actions)

        # Previously generated
        self._past_label = Gtk.Label(label="Recent reports", xalign=0)
        self._past_label.add_css_class("section-title")
        self.append(self._past_label)
        self._past_list = Gtk.ListBox()
        self._past_list.add_css_class("boxed-list")
        self._past_list.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(160); scroll.set_vexpand(True)
        scroll.set_child(self._past_list)
        self.append(scroll)
        self._refresh_past()

    # ── actions ───────────────────────────────────────────────────────────
    def _generate(self) -> None:
        if not self._workspaces:
            self._status_lbl.set_text("Create a workspace first.")
            return
        ws = self._workspaces[self._ws_dd.get_selected()]
        fmt = rep_svc.SUPPORTED_FORMATS[self._fmt_dd.get_selected()]
        custom = self._out_entry.get_text().strip()
        out_path = Path(custom).expanduser() if custom else None
        try:
            path = rep_svc.generate(ws.id, fmt, out_path)
        except Exception as e:
            self._status_lbl.set_text(f"failed: {e}")
            return
        self._status_lbl.set_text(f"wrote {path}")
        toaster = getattr(self._parent, "_toast_overlay", None)
        if toaster is not None:
            toast = Adw.Toast(title=f"Report saved: {path.name}")
            toast.set_button_label("Open folder")
            toast.connect("button-clicked", lambda *_: self._open_path(path.parent))
            toaster.add_toast(toast)
        self._refresh_past()

    def _refresh_past(self) -> None:
        child = self._past_list.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._past_list.remove(child)
            child = nxt
        out_dir = rep_svc.default_output_dir()
        if not out_dir.exists():
            self._past_list.append(Adw.ActionRow(
                title="No reports generated yet.",
                subtitle=str(out_dir)))
            return
        files = sorted(out_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:30]
        if not files:
            self._past_list.append(Adw.ActionRow(
                title="No reports generated yet.",
                subtitle=str(out_dir)))
            return
        for p in files:
            row = Adw.ActionRow(title=p.name, subtitle=str(p))
            open_btn = Gtk.Button.new_from_icon_name("folder-open-symbolic")
            open_btn.add_css_class("flat")
            open_btn.connect("clicked", lambda _b, x=p: self._open_path(x))
            row.add_suffix(open_btn)
            self._past_list.append(row)

    def _open_path(self, path: Path) -> None:
        try:
            Gio.AppInfo.launch_default_for_uri(f"file://{path}", None)
        except Exception:
            pass
