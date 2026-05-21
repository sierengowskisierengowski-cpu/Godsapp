"""Plugins view — list, enable/disable, install from path, remove."""
from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, Gtk  # noqa: E402

from godsapp.core import plugins as pl
from godsapp.ui.header_helpers import open_settings, page_header


class PluginsView(Gtk.Box):
    def __init__(self, parent) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(20); self.set_margin_bottom(20)
        self.set_margin_start(20); self.set_margin_end(20)
        self._parent = parent

        install_btn = Gtk.Button(label="Install from path…")
        install_btn.add_css_class("suggested-action")
        install_btn.connect("clicked", lambda *_: self._install_dialog())
        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.add_css_class("flat")
        refresh_btn.connect("clicked", lambda *_: self.refresh())

        self.append(page_header(
            "Plugins",
            on_settings=lambda: open_settings(parent, "plugins"),
            trailing=[refresh_btn, install_btn],
            subtitle=f"Plugin directory: {pl.plugins_dir()}",
        ))

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list.add_css_class("boxed-list")
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True); scroll.set_child(self._list)
        self.append(scroll)

        self._status_lbl = Gtk.Label(label="", xalign=0)
        self._status_lbl.add_css_class("dim-label")
        self.append(self._status_lbl)

        self.refresh()

    def refresh(self) -> None:
        child = self._list.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._list.remove(child)
            child = nxt
        plugins = pl.list_plugins()
        if not plugins:
            self._list.append(Adw.ActionRow(
                title="No plugins installed.",
                subtitle=f"Drop a Python package or .py file into {pl.plugins_dir()}, or click ‘Install from path’.",
            ))
            return
        for p in plugins:
            sub_bits = [f"v{p.version}"]
            if p.author: sub_bits.append(p.author)
            if p.tools_provided: sub_bits.append(f"tools: {', '.join(p.tools_provided)}")
            if p.error: sub_bits.append(f"⚠ {p.error}")
            row = Adw.ActionRow(
                title=p.name,
                subtitle=p.description or "  ·  ".join(sub_bits),
            )
            sw = Gtk.Switch()
            sw.set_active(p.enabled); sw.set_valign(Gtk.Align.CENTER)
            sw.connect("notify::active",
                       lambda s, _p, name=p.name: pl.set_enabled(name, s.get_active()))
            open_btn = Gtk.Button.new_from_icon_name("folder-open-symbolic")
            open_btn.add_css_class("flat")
            open_btn.connect("clicked",
                             lambda _b, x=p.path: Gio.AppInfo.launch_default_for_uri(f"file://{x}", None))
            del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
            del_btn.add_css_class("flat")
            del_btn.connect("clicked", lambda _b, name=p.name: self._remove(name))
            row.add_suffix(sw); row.add_suffix(open_btn); row.add_suffix(del_btn)
            self._list.append(row)

    def _remove(self, name: str) -> None:
        pl.remove(name)
        self.refresh()

    def _install_dialog(self) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_title("Select plugin file or directory")
        def on_open(_d, result) -> None:
            try:
                f = dialog.open_finish(result)
            except Exception:
                return
            if f is None: return
            try:
                pl.install_from_path(Path(f.get_path()))
                self._status_lbl.set_text(f"installed {Path(f.get_path()).name}")
            except Exception as e:
                self._status_lbl.set_text(f"install failed: {e}")
            self.refresh()
        dialog.open(self._parent, None, on_open)
