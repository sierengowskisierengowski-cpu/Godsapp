"""Command palette (Ctrl+K) — fuzzy navigate to any page, tool, or setting.

Author: Joseph Sierengowski.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gtk  # noqa: E402

from sqlalchemy import select

from godsapp.tools import registry


@dataclass
class Command:
    kind: str           # "page" | "tool" | "settings" | "action" |
                        # "finding" | "workspace" | "slash"
    key: str            # payload routed to MainWindow._on_select or callback id
    title: str
    subtitle: str
    keywords: str       # space-separated, lowercased


def _parse_tags(q: str) -> tuple[str, set[str]]:
    """Strip `#tag` tokens from a query; return (clean_query, tags)."""
    tags: set[str] = set()
    parts = []
    for tok in q.split():
        if tok.startswith("#") and len(tok) > 1:
            tags.add(tok[1:].lower())
        else:
            parts.append(tok)
    return " ".join(parts).strip(), tags


def _score(query: str, cmd: Command) -> int:
    """Tiny fuzzy scorer — substring on title gets the most weight, then keywords."""
    q = query.lower().strip()
    if not q:
        return 1
    # `#tag` filtering: command must contain the tag in keywords; clean query
    # then scores against the title/keywords as usual.
    clean, tags = _parse_tags(q)
    if tags:
        kw = cmd.keywords
        for t in tags:
            if t not in kw:
                return 0
        q = clean
        if not q:
            return 10  # tag-only match
    title = cmd.title.lower()
    if q == title:
        return 1000
    if title.startswith(q):
        return 500
    if q in title:
        return 300
    if q in cmd.keywords:
        return 100
    # all chars in order?
    i = 0
    for ch in title:
        if i < len(q) and ch == q[i]:
            i += 1
    if i == len(q):
        return 50
    return 0


class CommandPalette(Adw.Window):
    """Modal Ctrl-K palette. `on_pick(kind, key)` is called when the user hits Enter."""

    def __init__(self, parent: Gtk.Window,
                 commands: list[Command],
                 on_pick: Callable[[str, str], None]) -> None:
        super().__init__(transient_for=parent, modal=True)
        self.set_default_size(640, 460)
        self.set_decorated(False)
        self.add_css_class("cmd-palette")
        self._commands = commands
        self._filtered: list[Command] = list(commands)
        self._on_pick = on_pick

        wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        wrap.set_margin_top(2); wrap.set_margin_bottom(2)
        wrap.set_margin_start(2); wrap.set_margin_end(2)

        self._entry = Gtk.Entry()
        self._entry.add_css_class("cmd-input")
        self._entry.set_placeholder_text(
            "Jump to anything — tools, findings, workspaces · "
            "/slash · #critical · #high · #beginner")
        self._entry.connect("changed", lambda *_: self._refresh())
        self._entry.connect("activate", lambda *_: self._activate_selected())
        wrap.append(self._entry)

        sep = Gtk.Separator()
        wrap.append(sep)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.BROWSE)
        self._list.set_activate_on_single_click(True)
        self._list.add_css_class("cmd-palette-list")
        self._list.connect("row-activated", lambda _l, _r: self._activate_selected())
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True); scroll.set_child(self._list)
        wrap.append(scroll)

        self.set_content(wrap)

        # Esc closes; Up/Down navigate even while focus is in the Entry.
        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._on_key)
        self.add_controller(key)

        self._refresh()
        # Focus the entry once realized.
        self._entry.grab_focus()

    def _on_key(self, _ctrl, keyval, _kc, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.close(); return True
        if keyval == Gdk.KEY_Down:
            self._move(+1); return True
        if keyval == Gdk.KEY_Up:
            self._move(-1); return True
        return False

    def _move(self, delta: int) -> None:
        if not self._filtered:
            return
        cur = self._list.get_selected_row()
        idx = cur.get_index() if cur is not None else -1
        nxt = max(0, min(len(self._filtered) - 1, idx + delta))
        target = self._list.get_row_at_index(nxt)
        if target is not None:
            self._list.select_row(target)
            target.grab_focus()
            # immediately return focus to entry for continuous typing
            self._entry.grab_focus_without_selecting()

    def _refresh(self) -> None:
        q = self._entry.get_text() or ""
        scored = [(s, c) for c in self._commands if (s := _score(q, c)) > 0]
        scored.sort(key=lambda sc: (-sc[0], sc[1].kind, sc[1].title.lower()))
        self._filtered = [c for _s, c in scored[:120]]

        child = self._list.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._list.remove(child)
            child = nxt

        for c in self._filtered:
            self._list.append(self._make_row(c))

        first = self._list.get_row_at_index(0)
        if first is not None:
            self._list.select_row(first)

    def _make_row(self, c: Command) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row._cmd = c  # type: ignore[attr-defined]
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        kind = Gtk.Label(label=c.kind.upper()); kind.add_css_class("cmd-row-kind")
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label=c.title, xalign=0); title.add_css_class("cmd-row-title")
        title.set_hexpand(True)
        sub = Gtk.Label(label=c.subtitle, xalign=0); sub.add_css_class("cmd-row-sub")
        sub.set_ellipsize(3)
        text.append(title); text.append(sub)
        text.set_hexpand(True)
        box.append(kind); box.append(text)
        row.set_child(box)
        return row

    def extend_commands(self, more: list[Command]) -> None:
        """Append commands after the palette is already open (used for the
        lazy DB-backed sources so the palette doesn't block on disk I/O)."""
        if not more:
            return
        self._commands.extend(more)
        self._refresh()

    def _activate_selected(self) -> None:
        row = self._list.get_selected_row()
        if row is None and self._list.get_row_at_index(0) is not None:
            row = self._list.get_row_at_index(0)
        if row is None:
            return
        c = getattr(row, "_cmd", None)
        if c is None:
            return
        self.close()
        try:
            self._on_pick(c.kind, c.key)
        except Exception:
            pass


SLASH_COMMANDS: list[tuple[str, str, str]] = [
    # (slash key, title, subtitle)
    ("/tour",       "Re-launch onboarding tour",
     "Walk through every major view again."),
    ("/learn",      "Toggle Learn Mode",
     "Show inline tutorials inside every tool."),
    ("/help",       "Open command palette help",
     "Slash commands, tags (#critical), and shortcuts."),
    ("/terminal",   "Toggle terminal overlay",
     "Slide-down VTE shell. Same as double-clicking the title."),
    ("/refresh",    "Refresh current view",
     "Re-load the data for whatever's on screen (F5)."),
    ("/dashboard",  "Jump to Dashboard",
     "KPIs, severity bars, recent activity."),
]


def _build_dynamic_commands() -> list[Command]:
    """DB-backed sources: workspaces + recent findings. Safe to call from a
    worker thread — only touches a SQLAlchemy session and returns plain data."""
    cmds: list[Command] = []
    try:
        from godsapp.db import Finding, Workspace, get_session
        with get_session() as s:
            for ws in s.execute(
                    select(Workspace).order_by(Workspace.created_at.desc())
            ).scalars().all():
                cmds.append(Command(
                    kind="workspace", key=ws.id,
                    title=f"Workspace · {ws.name}",
                    subtitle=ws.description or ws.target or "Open the Workspaces view",
                    keywords=f"workspace {ws.name.lower()} "
                             f"{(ws.description or '').lower()} "
                             f"{(ws.target or '').lower()} #workspace",
                ))
            recents = s.execute(
                select(Finding).order_by(Finding.created_at.desc()).limit(200)
            ).scalars().all()
            for f in recents:
                sev = (f.severity or "info").lower()
                cmds.append(Command(
                    kind="finding", key=f.id,
                    title=f"[{sev.upper()}] {f.title}",
                    subtitle=f"{f.host or '—'}  ·  {f.service or ''}  ·  "
                             f"{(f.status or 'open')}",
                    keywords=f"finding {sev} {f.title.lower()} "
                             f"{(f.host or '').lower()} "
                             f"{(f.cve_ids or '').lower()} "
                             f"{(f.tags or '').lower()} "
                             f"#{sev} #{(f.status or 'open').lower()}",
                ))
    except Exception:
        pass
    return cmds


def build_commands(pinned_items: list[tuple[str, str, str]],
                   categories: list[tuple[str, str, str]],
                   *,
                   include_dynamic: bool = True) -> list[Command]:
    """Build the static + dynamic command list pulled from the registry,
    plus live database rows (findings, workspaces) and slash commands.

    When `include_dynamic=False`, the DB-backed sources are skipped — callers
    should then fetch them off the main thread and call `extend_commands()`.
    """
    cmds: list[Command] = []
    for key, title, _icon in pinned_items:
        cmds.append(Command(
            kind="page", key=key, title=title,
            subtitle="Pinned page",
            keywords=f"{key} {title.lower()} page",
        ))
    cat_titles = {cid: t for cid, t, _i in categories}
    for tool in registry.all():
        cat = cat_titles.get(tool.category, tool.category.title())
        diff = getattr(tool, "difficulty", "") or "intermediate"
        cmds.append(Command(
            kind="tool", key=tool.name,
            title=tool.title or tool.name,
            subtitle=f"{cat} · {tool.description or tool.requires_binary or ''}".strip(" ·"),
            keywords=f"{tool.name} {tool.category} {tool.title or ''} "
                    f"{tool.requires_binary or ''} {tool.description or ''} "
                    f"#{diff} tool".lower(),
        ))
    # Settings anchors
    for anchor, label in (
        ("general",    "Settings · General / UI / theme"),
        ("api",        "Settings · REST API"),
        ("scheduler",  "Settings · Scheduler"),
        ("terminal",   "Settings · Terminal"),
        ("threat",     "Settings · Threat intel API keys"),
        ("reports",    "Settings · Reports"),
        ("plugins",    "Settings · Plugins"),
        ("evidence",   "Settings · Evidence locker"),
        ("onboarding", "Settings · Onboarding & Tour"),
        ("learn",      "Settings · Learn Mode"),
        ("templates",  "Settings · Workspace Templates"),
        ("dedup",      "Settings · Findings Dedup"),
    ):
        cmds.append(Command(
            kind="settings", key=anchor, title=label,
            subtitle="Configure GodsApp",
            keywords=f"settings preferences {anchor} {label.lower()}",
        ))

    # Slash commands ─────────────────────────────────────────────────────
    for slash, title, sub in SLASH_COMMANDS:
        cmds.append(Command(
            kind="slash", key=slash, title=f"{slash}  {title}",
            subtitle=sub,
            keywords=f"slash {slash[1:]} {title.lower()} command action",
        ))

    if include_dynamic:
        cmds.extend(_build_dynamic_commands())
    return cmds
