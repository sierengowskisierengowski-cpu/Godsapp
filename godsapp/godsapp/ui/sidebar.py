"""Sidebar with live-search, expandable tool categories, and pinned items.

Author: Joseph Sierengowski.
"""
from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk  # noqa: E402

from godsapp.ui.matrix import attach as attach_scramble

SelectCallback = Callable[[str, str], None]  # (kind, payload)


class Sidebar(Gtk.Box):
    def __init__(self, on_select: SelectCallback) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("sidebar-root")
        self._on_select = on_select

        self._search = Gtk.SearchEntry()
        self._search.add_css_class("sidebar-search")
        self._search.set_placeholder_text("Filter tools…")
        self._search.connect("search-changed", lambda *_: self._apply_filter())
        self.append(self._search)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list.add_css_class("navigation-sidebar")
        self._list.connect("row-activated", self._on_row_activated)

        scrolled.set_child(self._list)
        self.append(scrolled)

    def focus_search(self) -> None:
        self._search.grab_focus()

    # ── populate ──────────────────────────────────────────────────────────
    def add_section(self, cat_id: str, title: str, icon: str, tools: list) -> None:
        header = self._make_header(title, icon, count=len(tools))
        header._search_text = f"{cat_id} {title}".lower()  # type: ignore[attr-defined]
        header._is_header = True  # type: ignore[attr-defined]
        self._list.append(header)
        for tool in tools:
            row = self._make_tool_row(tool)
            row._search_text = (  # type: ignore[attr-defined]
                f"{tool.name} {tool.title or ''} {tool.category} "
                f"{tool.description or ''} {tool.requires_binary or ''}").lower()
            self._list.append(row)

    def add_pinned(self, key: str, title: str, icon: str) -> None:
        row = Gtk.ListBoxRow()
        row.set_action_name(None)
        row.add_css_class("pinned-row")
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_top(8); box.set_margin_bottom(8)
        box.set_margin_start(12); box.set_margin_end(12)
        img = Gtk.Image.new_from_icon_name(icon)
        lbl = Gtk.Label(label=title, xalign=0)
        lbl.set_hexpand(True)
        attach_scramble(lbl)
        box.append(img); box.append(lbl)
        row.set_child(box)
        row._meta = ("pinned", key)  # type: ignore[attr-defined]
        row._search_text = f"{key} {title}".lower()  # type: ignore[attr-defined]
        self._list.append(row)

    def _make_header(self, title: str, icon: str, *, count: int) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.set_selectable(False); row.set_activatable(False)
        row.add_css_class("category-header")
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_top(12); box.set_margin_bottom(4)
        box.set_margin_start(10); box.set_margin_end(10)
        img = Gtk.Image.new_from_icon_name(icon); img.add_css_class("category-icon")
        lbl = Gtk.Label(label=title.upper(), xalign=0); lbl.add_css_class("category-label")
        lbl.set_hexpand(True); attach_scramble(lbl)
        count_lbl = Gtk.Label(label=str(count)); count_lbl.add_css_class("category-count")
        box.append(img); box.append(lbl); box.append(count_lbl)
        row.set_child(box)
        return row

    def _make_tool_row(self, tool) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.add_css_class("tool-row")
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_top(4); box.set_margin_bottom(4)
        box.set_margin_start(22); box.set_margin_end(12)
        dot = Gtk.Label(label="▸"); dot.add_css_class("tool-dot")
        name = Gtk.Label(label=tool.title or tool.name, xalign=0)
        name.set_hexpand(True); name.set_ellipsize(3)
        name.set_tooltip_text(tool.description or "")
        box.append(dot); box.append(name)
        row.set_child(box)
        row._meta = ("tool", tool.name)  # type: ignore[attr-defined]
        return row

    # ── filter ────────────────────────────────────────────────────────────
    def _apply_filter(self) -> None:
        q = (self._search.get_text() or "").lower().strip()
        child = self._list.get_first_child()
        while child is not None:
            text = getattr(child, "_search_text", "")
            if not q or q in text:
                child.set_visible(True)
            else:
                child.set_visible(False)
            child = child.get_next_sibling()

    def _on_row_activated(self, _list, row: Gtk.ListBoxRow) -> None:
        meta = getattr(row, "_meta", None)
        if meta is None:
            return
        kind, payload = meta
        self._on_select(kind, payload)
