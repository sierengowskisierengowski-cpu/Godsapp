"""Reusable header widgets: page title rows with a settings-cog shortcut.

Every primary view gets a top-right gear that navigates to the master
Settings view. (Per-category settings sub-pages are queued for the next
wave — see STATUS.md.)  Author: Joseph Sierengowski.
"""
from __future__ import annotations

from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk  # noqa: E402

from godsapp.ui.matrix import attach as attach_scramble


def page_header(title: str,
                on_settings: Optional[Callable[[], None]] = None,
                *,
                trailing: Optional[list[Gtk.Widget]] = None,
                subtitle: Optional[str] = None) -> Gtk.Widget:
    """A standardised page header: title (matrix-scramble on hover) + optional
    trailing buttons + a settings cog that jumps to Settings."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    lbl = Gtk.Label(label=title, xalign=0)
    lbl.add_css_class("view-title")
    lbl.set_hexpand(True)
    attach_scramble(lbl)
    row.append(lbl)

    if trailing:
        for w in trailing:
            row.append(w)

    if on_settings is not None:
        gear = Gtk.Button.new_from_icon_name("emblem-system-symbolic")
        gear.add_css_class("flat")
        gear.set_tooltip_text("Open settings for this page")
        gear.connect("clicked", lambda *_: on_settings())
        row.append(gear)

    box.append(row)

    if subtitle:
        sub = Gtk.Label(label=subtitle, xalign=0)
        sub.add_css_class("hero-sub")
        sub.set_wrap(True)
        box.append(sub)

    return box


def open_settings(parent) -> None:
    """Helper a view can hand to page_header: navigates the main window to
    the Settings view. Tolerant to detached/uninitialised parents."""
    try:
        parent._on_select("pinned", "settings")  # type: ignore[attr-defined]
    except Exception:
        pass
