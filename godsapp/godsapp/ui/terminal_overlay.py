"""TerminalOverlay — slide-down embedded VTE terminal with ASCII Olympus
header, live status line, persistent shell session, and a WOW entry effect
that triggers a rapid lightning storm + thunder boom.

Revealed by double-clicking the GodsApp title in the header.
Author: Joseph Sierengowski.
"""
from __future__ import annotations

import os
import socket
import time
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GLib, Gtk, Pango  # noqa: E402

from godsapp import __app_name__, __version__
from godsapp.core import paths
from godsapp.core.logging import get_logger
from godsapp.core.scans import runner
from godsapp.core.settings import load_settings

log = get_logger(__name__)

try:
    gi.require_version("Vte", "3.91")
    from gi.repository import Vte  # type: ignore
    HAVE_VTE = True
except (ValueError, ImportError):
    try:
        gi.require_version("Vte", "2.91")
        from gi.repository import Vte  # type: ignore
        HAVE_VTE = True
    except (ValueError, ImportError):
        Vte = None  # type: ignore
        HAVE_VTE = False

try:
    import psutil  # type: ignore
    HAVE_PSUTIL = True
except Exception:
    psutil = None  # type: ignore
    HAVE_PSUTIL = False


# ── Olympus-cream palette for the VTE color scheme ──────────────────────
_SCHEMES = {
    "godsapp": dict(
        bg=(0.02, 0.04, 0.08, 0.85),
        fg=(0.96, 0.97, 0.99, 1.0),
        palette=[
            (0.05,0.07,0.12,1), (0.95,0.30,0.30,1), (0.55,0.85,0.55,1), (1.0,0.85,0.45,1),
            (0.50,0.75,1.00,1), (0.85,0.60,1.00,1), (0.55,0.95,0.95,1), (0.86,0.86,0.86,1),
            (0.35,0.40,0.50,1), (1.00,0.50,0.50,1), (0.70,1.00,0.70,1), (1.00,0.95,0.65,1),
            (0.65,0.85,1.00,1), (0.95,0.75,1.00,1), (0.75,1.00,1.00,1), (1.00,1.00,1.00,1),
        ],
    ),
    "dracula": dict(
        bg=(0.157,0.165,0.212,0.92), fg=(0.973,0.973,0.949,1.0),
        palette=[],
    ),
    "solarized": dict(
        bg=(0.000,0.169,0.212,0.92), fg=(0.514,0.580,0.588,1.0),
        palette=[],
    ),
    "nord": dict(
        bg=(0.180,0.204,0.251,0.92), fg=(0.847,0.871,0.914,1.0),
        palette=[],
    ),
    "gruvbox": dict(
        bg=(0.157,0.157,0.157,0.92), fg=(0.922,0.859,0.698,1.0),
        palette=[],
    ),
}


def _rgba(*c) -> Gdk.RGBA:
    r = Gdk.RGBA(); r.red, r.green, r.blue, r.alpha = c
    return r


class TerminalOverlay(Gtk.Revealer):
    """Slide-down terminal overlay. Held by MainWindow; toggled by double-click."""

    SLIDE_MS = 380

    def __init__(self, main_window) -> None:
        super().__init__()
        self._main = main_window
        self.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.set_transition_duration(self.SLIDE_MS)
        self.set_reveal_child(False)
        self.set_halign(Gtk.Align.FILL)
        self.set_valign(Gtk.Align.START)
        self.set_hexpand(True); self.set_vexpand(False)
        self.add_css_class("terminal-overlay")

        # Container
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._box.set_hexpand(True); self._box.set_vexpand(True)
        self._box.add_css_class("terminal-overlay-body")

        # Pinned ASCII header (above the VTE)
        self._header_box = self._build_header()
        self._box.append(self._header_box)

        # Live status line (also pinned)
        self._status_label = Gtk.Label(xalign=0.0)
        self._status_label.add_css_class("terminal-status-line")
        self._status_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._status_label.set_margin_start(18); self._status_label.set_margin_end(18)
        self._status_label.set_margin_bottom(8)
        self._box.append(self._status_label)

        # VTE area (lazy-spawned on first reveal)
        self._term: Gtk.Widget | None = None
        self._term_scroll = Gtk.ScrolledWindow()
        self._term_scroll.set_hexpand(True); self._term_scroll.set_vexpand(True)
        self._term_scroll.add_css_class("terminal-screen")
        self._box.append(self._term_scroll)

        # Size: take 78% of the window height when revealed
        self.set_child(self._box)
        self._main.connect("notify::default-height", lambda *_: self._resize_to_window())
        self._main.connect("realize", lambda *_: self._resize_to_window())

        # Live tickers (status line: 1s; ascii pulse handled by CSS)
        self._status_tick_id = 0
        self._spawned = False
        self._log_path: Path | None = None

    # ── header ──────────────────────────────────────────────────────────
    def _build_header(self) -> Gtk.Widget:
        wrap = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                       halign=Gtk.Align.CENTER)
        wrap.add_css_class("terminal-ascii-wrap")
        wrap.set_margin_top(14); wrap.set_margin_bottom(6)
        wrap.set_margin_start(18); wrap.set_margin_end(18)

        for ch in ("⚡", "⚡", "⚡"):
            b = Gtk.Label(label=ch)
            b.add_css_class("ascii-bolt"); b.add_css_class("ascii-bolt-left")
            wrap.append(b)

        ascii_lines = [
            "  ▄████   ▒█████   ▓█████▄   ██████  ▄▄▄       ██▓███   ██▓███",
            " ██▒ ▀█▒ ▒██▒  ██▒ ▒██▀ ██▌▒██    ▒ ▒████▄    ▓██░  ██▒▓██░  ██▒",
            "▒██░▄▄▄░ ▒██░  ██▒ ░██   █▌░ ▓██▄   ▒██  ▀█▄  ▓██░ ██▓▒▓██░ ██▓▒",
            "░▓█  ██▓ ▒██   ██░ ░▓█▄   ▌  ▒   ██▒░██▄▄▄▄██ ▒██▄█▓▒ ▒▒██▄█▓▒ ▒",
            "░▒▓███▀▒ ░ ████▓▒░ ░▒████▓ ▒██████▒▒ ▓█   ▓██▒▒██▒ ░  ░▒██▒ ░  ░",
        ]
        ascii_lbl = Gtk.Label(label="\n".join(ascii_lines))
        ascii_lbl.add_css_class("terminal-ascii")
        ascii_lbl.set_use_markup(False)
        wrap.append(ascii_lbl)

        for ch in ("⚡", "⚡", "⚡"):
            b = Gtk.Label(label=ch)
            b.add_css_class("ascii-bolt"); b.add_css_class("ascii-bolt-right")
            wrap.append(b)

        return wrap

    # ── sizing ──────────────────────────────────────────────────────────
    def _resize_to_window(self) -> None:
        h = self._main.get_height() or self._main.get_default_size()[1]
        if h and h > 200:
            # Headerbar is ~46px; take everything below.
            self._box.set_size_request(-1, int(h - 60))

    # ── public toggle (called from MainWindow double-click) ─────────────
    def toggle(self) -> None:
        if self.get_reveal_child():
            self.hide_terminal()
        else:
            self.show_terminal()

    def show_terminal(self) -> None:
        if not self._spawned:
            self._spawn()
            self._spawned = True
        self._resize_to_window()
        self.set_reveal_child(True)
        # WOW: trigger storm + state-running window pulse + grab focus
        try:
            if getattr(self._main, "_storm", None) is not None:
                self._main._storm.intense_burst(count=6, with_boom=True)
        except Exception:
            log.exception("storm burst failed")
        try:
            self._main.add_css_class("screen-pulse")
            GLib.timeout_add(1600, lambda: (self._main.remove_css_class("screen-pulse"), False)[1])
        except Exception:
            pass
        # Focus the terminal once the slide finishes
        def _focus():
            try:
                if self._term is not None:
                    self._term.grab_focus()
            except Exception:
                pass
            return False
        GLib.timeout_add(self.SLIDE_MS + 30, _focus)
        # Start status line ticker
        if self._status_tick_id == 0:
            self._status_tick_id = GLib.timeout_add_seconds(1, self._tick_status)
        self._tick_status()

    def hide_terminal(self) -> None:
        self.set_reveal_child(False)
        if self._status_tick_id:
            try:
                GLib.source_remove(self._status_tick_id)
            except Exception:
                pass
            self._status_tick_id = 0

    # ── VTE spawn ───────────────────────────────────────────────────────
    def _spawn(self) -> None:
        if not HAVE_VTE:
            self._term_scroll.set_child(self._fallback_widget())
            return
        s = load_settings().terminal
        term = Vte.Terminal()
        try:
            term.set_font(Pango.FontDescription.from_string(s.font or "Monospace 11"))
        except Exception:
            pass
        try:
            term.set_scrollback_lines(int(s.scrollback_lines or 50000))
        except Exception:
            pass
        try:
            term.set_cursor_blink_mode(
                Vte.CursorBlinkMode.ON if s.cursor_blink else Vte.CursorBlinkMode.OFF
            )
        except Exception:
            pass
        # Color scheme
        try:
            sch = _SCHEMES.get(s.color_scheme, _SCHEMES["godsapp"])
            palette = [_rgba(*c) for c in sch.get("palette") or []] or None
            term.set_colors(_rgba(*sch["fg"]), _rgba(*sch["bg"]), palette)
        except Exception:
            log.exception("vte set_colors failed")

        shell = (s.shell or os.environ.get("SHELL") or "/bin/bash").strip()
        cwd = self._resolve_cwd()

        # Inject GodsApp context env vars
        extra_env = self._build_env(cwd)
        env_list = [f"{k}={v}" for k, v in {**os.environ, **extra_env}.items()]

        try:
            term.spawn_async(
                Vte.PtyFlags.DEFAULT,
                cwd,
                [shell],
                env_list,
                GLib.SpawnFlags.DEFAULT,
                None, None,
                -1, None, None, None,
            )
        except Exception:
            try:
                term.spawn_sync(
                    Vte.PtyFlags.DEFAULT, cwd, [shell], env_list,
                    GLib.SpawnFlags.DEFAULT, None, None, None,
                )
            except Exception as e:
                err = Gtk.Label(label=f"failed to spawn shell: {e}")
                self._term_scroll.set_child(err)
                return

        # Workspace logging — VTE can mirror its output to a file.
        if s.workspace_logging:
            try:
                self._log_path = self._setup_logging(term)
            except Exception:
                log.exception("workspace logging setup failed")

        self._term = term
        self._term_scroll.set_child(term)

    def _fallback_widget(self) -> Gtk.Widget:
        warn = Adw.PreferencesGroup(title="Embedded terminal unavailable")
        row = Adw.ActionRow(
            title="libvte 3.91 / 2.91 is not installed",
            subtitle=("Install the system package and restart GodsApp:\n"
                      "  • Arch:    sudo pacman -S vte4 vte-common\n"
                      "  • Fedora:  sudo dnf install vte291-gtk4\n"
                      "  • Debian:  sudo apt install gir1.2-vte-3.91"),
        )
        warn.add(row)
        page = Adw.PreferencesPage(); page.add(warn)
        return page

    def _resolve_cwd(self) -> str:
        try:
            home = os.environ.get("HOME") or "/"
            base = paths.user_data_dir() / "workspaces"
            if base.exists():
                # Most recent workspace dir
                subs = sorted(base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
                for s in subs:
                    if s.is_dir():
                        ev = s / "evidence"
                        return str(ev if ev.exists() else s)
            return home
        except Exception:
            return os.environ.get("HOME") or "/"

    def _build_env(self, cwd: str) -> dict[str, str]:
        env: dict[str, str] = {"GODSAPP_VERSION": __version__}
        try:
            base = paths.user_data_dir() / "workspaces"
            if base.exists():
                subs = sorted([p for p in base.iterdir() if p.is_dir()],
                              key=lambda p: p.stat().st_mtime, reverse=True)
                if subs:
                    ws = subs[0]
                    env["GODSAPP_WORKSPACE"] = ws.name
                    env["GODSAPP_WORKSPACE_NAME"] = ws.name
                    env["GODSAPP_EVIDENCE_DIR"] = str(ws / "evidence")
        except Exception:
            pass
        env.setdefault("GODSAPP_WORKSPACE", "default")
        env.setdefault("GODSAPP_EVIDENCE_DIR", cwd)
        try:
            api = load_settings().api
            if api.enabled:
                env["GODSAPP_FINDINGS_API"] = f"http://{api.host}:{api.port}/findings"
        except Exception:
            pass
        return env

    def _setup_logging(self, term) -> Path | None:
        log_dir = paths.user_data_dir() / "workspaces" / "_global" / "terminal"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"session-{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.log"
        # VTE doesn't have a built-in tee; the simplest reliable approach
        # is to snapshot the buffer on hide. Connect to "contents-changed"
        # and write incremental deltas would be ideal but heavy; we just
        # record the path so a future tab can flush.
        # For now, ensure the file exists and is owned by the user.
        path.touch()
        return path

    # ── status line ─────────────────────────────────────────────────────
    def _tick_status(self) -> bool:
        try:
            now = datetime.now().strftime("%a %b %d  %H:%M:%S")
            host = socket.gethostname()
            user = os.environ.get("USER") or os.environ.get("LOGNAME") or "user"
            parts = [f"{now}", f"{user}@{host}"]
            if HAVE_PSUTIL:
                try:
                    cpu = psutil.cpu_percent(interval=None)
                    mem = psutil.virtual_memory().percent
                    parts.append(f"CPU {cpu:4.1f}%")
                    parts.append(f"RAM {mem:4.1f}%")
                except Exception:
                    pass
            # Scan/finding counts from the runner
            try:
                active = len(runner.active_scans()) if hasattr(runner, "active_scans") else 0
            except Exception:
                active = 0
            parts.append(f"scans:{active}")
            parts.append(f"v{__version__}")
            self._status_label.set_markup(
                "  ·  ".join(f"<span color='#f0d27a'>{p}</span>" if p.startswith(("CPU","RAM","scans"))
                              else f"<span color='#dfe7f5'>{p}</span>"
                              for p in parts)
            )
        except Exception:
            log.exception("status tick failed")
        return True
