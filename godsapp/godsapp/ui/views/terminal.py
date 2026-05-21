"""Embedded VTE terminal — multi-tab, configurable shell + font.

Falls back gracefully with an actionable message when libvte-3-gir is missing.
Author: Joseph Sierengowski.
"""
from __future__ import annotations

import os
import shlex

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from godsapp.core.settings import load_settings
from godsapp.ui.header_helpers import open_settings, page_header

# Optional libvte
try:
    gi.require_version("Vte", "3.91")
    from gi.repository import Vte  # type: ignore
    HAVE_VTE = True
except (ValueError, ImportError):
    Vte = None  # type: ignore
    HAVE_VTE = False


class TerminalView(Gtk.Box):
    def __init__(self, parent) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_margin_top(20); self.set_margin_bottom(20)
        self.set_margin_start(20); self.set_margin_end(20)
        self._parent = parent
        self._tab_count = 0

        new_btn = Gtk.Button(label="New tab")
        new_btn.add_css_class("suggested-action")
        new_btn.connect("clicked", lambda *_: self._add_tab())

        self.append(page_header(
            "Terminal",
            on_settings=lambda: open_settings(parent, "terminal"),
            trailing=[new_btn],
            subtitle="A real PTY (VTE 3.91). Shell, font, and scrollback live in Settings → Terminal.",
        ))

        if not HAVE_VTE:
            self._show_fallback()
            return

        self._notebook = Gtk.Notebook()
        self._notebook.set_scrollable(True)
        self._notebook.set_vexpand(True)
        self.append(self._notebook)
        self._add_tab()

    def _show_fallback(self) -> None:
        warn = Adw.PreferencesGroup(title="Embedded terminal unavailable")
        row = Adw.ActionRow(
            title="libvte 3.91 is not installed",
            subtitle=("Install the system package and restart GodsApp:\n"
                      "  • Arch:    sudo pacman -S vte-common gtk4-vte (or vte4)\n"
                      "  • Fedora:  sudo dnf install vte291-gtk4\n"
                      "  • Debian:  sudo apt install gir1.2-vte-3.91"),
        )
        warn.add(row)
        page = Adw.PreferencesPage(); page.add(warn)
        self.append(page)

    def _add_tab(self) -> None:
        if not HAVE_VTE:
            return
        self._tab_count += 1
        s = load_settings()
        term = Vte.Terminal()
        try:
            from gi.repository import Pango
            term.set_font(Pango.FontDescription.from_string(s.terminal.font or "Monospace 11"))
        except Exception:
            pass
        try:
            term.set_scrollback_lines(int(s.terminal.scrollback_lines or 10000))
        except Exception:
            pass

        # Spawn shell
        shell = (s.terminal.shell or os.environ.get("SHELL") or "/bin/bash").strip()
        argv = [shell]
        # Vte 3.91 API
        try:
            term.spawn_async(
                Vte.PtyFlags.DEFAULT,
                os.environ.get("HOME") or "/",
                argv,
                [],                          # env (use parent)
                GLib.SpawnFlags.DEFAULT,
                None, None,                  # child_setup, child_setup_data
                -1, None, None, None,
            )
        except Exception:
            # Older signatures
            try:
                term.spawn_sync(
                    Vte.PtyFlags.DEFAULT,
                    os.environ.get("HOME") or "/",
                    argv,
                    [],
                    GLib.SpawnFlags.DEFAULT,
                    None, None, None,
                )
            except Exception as e:
                err_lbl = Gtk.Label(label=f"failed to spawn shell: {e}")
                self._notebook.append_page(err_lbl, Gtk.Label(label=f"Tab {self._tab_count}"))
                return

        scroll = Gtk.ScrolledWindow()
        scroll.set_hexpand(True); scroll.set_vexpand(True)
        scroll.set_child(term)

        tab_label = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tab_label.append(Gtk.Label(label=f"Tab {self._tab_count}"))
        close = Gtk.Button.new_from_icon_name("window-close-symbolic")
        close.add_css_class("flat")
        close.connect("clicked", lambda *_: self._notebook.remove_page(
            self._notebook.page_num(scroll)))
        tab_label.append(close)

        page_index = self._notebook.append_page(scroll, tab_label)
        self._notebook.set_current_page(page_index)
