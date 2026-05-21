"""First-launch Onboarding Tour.

A center-screen card walking the user through the major surfaces of GodsApp:
workspaces, scanning, findings, evidence, command palette, terminal, and
settings. Fully skippable. Persists the "completed" flag so it doesn't fire
again unless explicitly reset from Settings → Onboarding.

The current implementation uses a sequential card overlay rather than UI
spotlights — the cards reference each surface by name and provide a "Take me
there" button that calls into the parent MainWindow. We'll add real spotlight
highlighting in v0.4.1 once the tour content has stabilised.

Author: Joseph Sierengowski.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from godsapp import __app_name__, __version__
from godsapp.core.logging import get_logger
from godsapp.core.settings import load_settings, save_settings

log = get_logger(__name__)


@dataclass
class TourStep:
    title: str
    body: str
    cta_label: str = ""
    cta_target: str = ""   # MainWindow stack page key, or "palette", or ""


TOUR_STEPS: list[TourStep] = [
    TourStep(
        title="Welcome to GodsApp",
        body=("Olympus-grade security suite. Twelve tool categories, evidence "
              "locker with chain of custody, findings triage, scheduler, REST "
              "API, embedded terminal, plugin system. This 60-second tour shows "
              "you the doors. You can skip and come back any time from "
              "Settings → Onboarding."),
        cta_label="Begin the tour",
    ),
    TourStep(
        title="Workspaces — your engagement container",
        body=("Every scan, finding, and piece of evidence lives in a workspace. "
              "Start with the built-in templates (Bug Bounty, Pentest, CTF, "
              "Forensics…) which pre-fill scope, tags, and a welcome note."),
        cta_label="Open Workspaces",
        cta_target="workspaces",
    ),
    TourStep(
        title="The Sidebar — every tool, two clicks away",
        body=("Twelve categories: Recon, Web, Network, Password, Exploit, "
              "Wireless, Forensics, Malware, OSINT, Crypto, Mobile, Cloud. "
              "Coloured difficulty dots tell you what you're getting into. "
              "Type in the filter at the top to find anything fast."),
        cta_label="Focus the sidebar search",
        cta_target="focus-sidebar",
    ),
    TourStep(
        title="Findings — triage every result",
        body=("Tool output is auto-parsed into findings. Sort by severity, "
              "filter by status, link related findings, merge duplicates, "
              "export to CSV. Each finding carries CVSS / CVE / MITRE."),
        cta_label="Open Findings Manager",
        cta_target="findings",
    ),
    TourStep(
        title="Evidence Locker — content-addressed, chain-of-custody",
        body=("Every artifact stored as sha256[:2]/sha256.<ext>. Duplicate "
              "ingests collapse automatically. Verify integrity any time."),
        cta_label="Open Evidence",
        cta_target="evidence",
    ),
    TourStep(
        title="Command Palette — Ctrl + K does anything",
        body=("Jump to any page, tool, finding, workspace, or settings anchor. "
              "Slash commands: /find <query>, /scan <tool> <target>, /tour. "
              "Tag filters: #critical, #high. It's the fastest way to navigate."),
        cta_label="Open Command Palette",
        cta_target="palette",
    ),
    TourStep(
        title="Summon the Terminal — double-click the title bar",
        body=("Double-click 'GODSAPP' in the header to drop a real VTE shell "
              "from the top of the window. Persistent across hide/show. "
              "Environment vars include $GODSAPP_WORKSPACE and $GODSAPP_EVIDENCE_DIR."),
        cta_label="Got it",
    ),
    TourStep(
        title="You're ready",
        body=("Re-run this tour any time from Settings → Onboarding. "
              "Toggle Learn Mode on from Settings → Learn for inline tutorials "
              "inside every tool. Have a stormy day."),
        cta_label="Enter the realm",
    ),
]


class OnboardingWindow(Adw.Window):
    """A centred modal walking the user through TOUR_STEPS."""

    def __init__(self, parent: Gtk.Window, *,
                 on_jump: Callable[[str], None],
                 on_done: Callable[[], None] | None = None) -> None:
        # Non-modal by design: the tour's "Open Workspaces / palette / focus
        # sidebar" CTAs need the main window to remain interactive. The
        # singleton guard in MainWindow.show_onboarding() prevents stacking.
        super().__init__(transient_for=parent, modal=False)
        self.set_default_size(580, 480)
        self.set_decorated(False)
        self.add_css_class("godsapp-window")
        self.add_css_class("onboarding-window")
        self._on_jump = on_jump
        self._on_done = on_done
        self._idx = 0

        toolbar = Adw.ToolbarView()
        hb = Adw.HeaderBar()
        hb.add_css_class("flat")
        title = Gtk.Label(label=f"{__app_name__} · Guided Tour")
        title.add_css_class("onboarding-titlebar")
        hb.set_title_widget(title)
        close_btn = Gtk.Button(label="Skip tour")
        close_btn.add_css_class("flat")
        close_btn.connect("clicked", lambda *_: self._finish(persist=True))
        hb.pack_end(close_btn)
        toolbar.add_top_bar(hb)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        body.set_margin_top(20); body.set_margin_bottom(24)
        body.set_margin_start(36); body.set_margin_end(36)
        body.set_hexpand(True); body.set_vexpand(True)

        self._dots = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                             spacing=6, halign=Gtk.Align.CENTER)
        body.append(self._dots)

        self._title_lbl = Gtk.Label(xalign=0.0)
        self._title_lbl.add_css_class("onboarding-step-title")
        self._title_lbl.set_wrap(True)
        body.append(self._title_lbl)

        self._body_lbl = Gtk.Label(xalign=0.0)
        self._body_lbl.add_css_class("onboarding-step-body")
        self._body_lbl.set_wrap(True)
        self._body_lbl.set_vexpand(True)
        self._body_lbl.set_yalign(0.0)
        body.append(self._body_lbl)

        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        nav.set_halign(Gtk.Align.FILL)
        self._back_btn = Gtk.Button(label="Back")
        self._back_btn.connect("clicked", lambda *_: self._step(-1))
        self._cta_btn = Gtk.Button(label="Next")
        self._cta_btn.add_css_class("suggested-action")
        self._cta_btn.connect("clicked", lambda *_: self._cta())
        self._next_btn = Gtk.Button(label="Next →")
        self._next_btn.connect("clicked", lambda *_: self._step(+1))
        spacer = Gtk.Box(); spacer.set_hexpand(True)
        nav.append(self._back_btn); nav.append(spacer)
        nav.append(self._cta_btn); nav.append(self._next_btn)
        body.append(nav)

        toolbar.set_content(body)
        self.set_content(toolbar)

        # Esc/Enter shortcuts
        key = Gtk.EventControllerKey.new()
        key.connect("key-pressed", self._on_key)
        self.add_controller(key)

        self._render()

    def _on_key(self, _ctrl, keyval, _kc, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self._finish(persist=True); return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_Right):
            self._step(+1); return True
        if keyval == Gdk.KEY_Left:
            self._step(-1); return True
        return False

    def _render(self) -> None:
        # progress dots
        child = self._dots.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._dots.remove(child)
            child = nxt
        for i in range(len(TOUR_STEPS)):
            d = Gtk.Label(label="●")
            d.add_css_class("onboarding-dot")
            if i == self._idx:
                d.add_css_class("active")
            self._dots.append(d)

        step = TOUR_STEPS[self._idx]
        self._title_lbl.set_text(step.title)
        self._body_lbl.set_text(step.body)
        self._back_btn.set_sensitive(self._idx > 0)
        is_last = self._idx == len(TOUR_STEPS) - 1
        self._next_btn.set_label("Finish" if is_last else "Next →")

        if step.cta_label and step.cta_target:
            self._cta_btn.set_label(step.cta_label)
            self._cta_btn.set_visible(True)
        else:
            self._cta_btn.set_visible(False)

    def _step(self, delta: int) -> None:
        new = self._idx + delta
        if new < 0:
            return
        if new >= len(TOUR_STEPS):
            self._finish(persist=True)
            return
        self._idx = new
        self._render()

    def _cta(self) -> None:
        step = TOUR_STEPS[self._idx]
        if step.cta_target:
            try:
                self._on_jump(step.cta_target)
            except Exception:
                log.exception("onboarding jump failed: %s", step.cta_target)

    def _finish(self, *, persist: bool) -> None:
        if persist:
            try:
                s = load_settings()
                s.onboarding.completed = True
                save_settings(s)
            except Exception:
                log.exception("failed to persist onboarding.completed")
        try:
            if self._on_done is not None:
                self._on_done()
        finally:
            self.close()


def maybe_show_tour(parent_window, *,
                    on_jump: Callable[[str], None],
                    force: bool = False) -> OnboardingWindow | None:
    """Show the tour on first launch (or whenever the completed flag is False)."""
    try:
        s = load_settings()
        if not force and getattr(s.onboarding, "completed", False):
            return None
        if not force and not getattr(s.onboarding, "enabled", True):
            return None
    except Exception:
        if not force:
            return None
    win = OnboardingWindow(parent_window, on_jump=on_jump)
    GLib.idle_add(win.present)
    return win
