"""API Console view — toggle the REST server, manage the auth token, tail logs."""
from __future__ import annotations

import secrets
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from godsapp.core import paths
from godsapp.core.settings import load_settings, save_settings
from godsapp.ui.header_helpers import open_settings, page_header


class ApiConsoleView(Gtk.Box):
    def __init__(self, parent) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(20); self.set_margin_bottom(20)
        self.set_margin_start(20); self.set_margin_end(20)
        self._parent = parent
        self._server_thread: threading.Thread | None = None
        self._server = None

        self.append(page_header(
            "API Console",
            on_settings=lambda: open_settings(parent, "api"),
            subtitle="Start / stop the local REST server, rotate the auth token, and tail recent log lines.",
        ))

        # Status row
        self._status_lbl = Gtk.Label(label="checking…", xalign=0)
        self._status_lbl.add_css_class("section-title")
        self.append(self._status_lbl)

        # Controls
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        start_btn = Gtk.Button(label="Start server")
        start_btn.add_css_class("suggested-action")
        start_btn.connect("clicked", lambda *_: self._start_server())
        stop_btn = Gtk.Button(label="Stop server")
        stop_btn.add_css_class("destructive-action")
        stop_btn.connect("clicked", lambda *_: self._stop_server())
        controls.append(start_btn); controls.append(stop_btn)
        self.append(controls)

        # Token panel
        token_g = Adw.PreferencesGroup(title="Auth token", description=str(paths.API_TOKEN_PATH))
        self._token_row = Adw.EntryRow(title="Current token")
        self._token_row.set_text(self._read_token())
        token_g.add(self._token_row)
        regen_btn = Gtk.Button(label="Regenerate token")
        regen_btn.connect("clicked", lambda *_: self._regen_token())
        copy_btn = Gtk.Button(label="Copy token")
        copy_btn.connect("clicked", lambda *_: self._copy_token())
        bb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bb.append(regen_btn); bb.append(copy_btn)
        wrap = Adw.PreferencesGroup(); wrap.add(bb)
        self.append(token_g); self.append(wrap)

        # Log tail
        log_label = Gtk.Label(label="Recent API log lines", xalign=0)
        log_label.add_css_class("section-title")
        self.append(log_label)
        self._log_buf = Gtk.TextBuffer()
        log_view = Gtk.TextView.new_with_buffer(self._log_buf)
        log_view.set_editable(False); log_view.set_monospace(True)
        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_min_content_height(220); log_scroll.set_vexpand(True)
        log_scroll.set_child(log_view)
        self.append(log_scroll)
        refresh_btn = Gtk.Button(label="Refresh log")
        refresh_btn.connect("clicked", lambda *_: self._refresh_log())
        self.append(refresh_btn)

        self._refresh_status()
        self._refresh_log()
        GLib.timeout_add_seconds(5, self._refresh_status)

    # ── helpers ───────────────────────────────────────────────────────────
    def _read_token(self) -> str:
        try:
            return paths.API_TOKEN_PATH.read_text().strip()
        except FileNotFoundError:
            return ""

    def _refresh_status(self) -> bool:
        s = load_settings()
        running = self._server is not None
        url = f"http://{s.api.host}:{s.api.port}"
        self._status_lbl.set_text(
            f"{'● running' if running else '○ stopped'}   "
            f"·  {url}  ·  token: {'required' if s.api.require_token else 'optional'}"
        )
        return True

    def _regen_token(self) -> None:
        tok = secrets.token_urlsafe(32)
        paths.ensure_directories()
        paths.API_TOKEN_PATH.write_text(tok + "\n")
        try:
            paths.API_TOKEN_PATH.chmod(0o600)
        except Exception:
            pass
        self._token_row.set_text(tok)
        toaster = getattr(self._parent, "_toast_overlay", None)
        if toaster is not None:
            toaster.add_toast(Adw.Toast(title="API token rotated"))

    def _copy_token(self) -> None:
        token = self._token_row.get_text()
        try:
            from gi.repository import Gdk
            display = Gdk.Display.get_default()
            clip = display.get_clipboard()
            clip.set(token)
        except Exception:
            pass
        toaster = getattr(self._parent, "_toast_overlay", None)
        if toaster is not None:
            toaster.add_toast(Adw.Toast(title="Token copied to clipboard"))

    def _refresh_log(self) -> None:
        log_path = paths.LOG_DIR / "api.log"
        if not log_path.exists():
            self._log_buf.set_text(f"(no log file at {log_path})")
            return
        try:
            text = log_path.read_text()[-20_000:]
        except Exception as e:
            text = f"failed to read log: {e}"
        self._log_buf.set_text(text)

    # ── server lifecycle ──────────────────────────────────────────────────
    def _start_server(self) -> None:
        if self._server is not None:
            return
        try:
            import uvicorn
            from godsapp.api.server import app as api_app
        except Exception as e:
            self._status_lbl.set_text(f"failed to import API: {e}")
            return
        s = load_settings()
        config = uvicorn.Config(
            api_app, host=s.api.host, port=s.api.port,
            log_level="info", access_log=False, loop="asyncio",
        )
        self._server = uvicorn.Server(config)

        def runme():
            import asyncio
            try:
                asyncio.run(self._server.serve())
            except Exception:
                pass
            finally:
                self._server = None

        self._server_thread = threading.Thread(target=runme, daemon=True, name="godsapp-api")
        self._server_thread.start()
        # Also flip persisted setting so it shows enabled
        s.api.enabled = True
        save_settings(s)
        self._refresh_status()
        toaster = getattr(self._parent, "_toast_overlay", None)
        if toaster is not None:
            toaster.add_toast(Adw.Toast(title=f"API listening on {s.api.host}:{s.api.port}"))

    def _stop_server(self) -> None:
        if self._server is None:
            return
        try:
            self._server.should_exit = True
        except Exception:
            pass
        self._server = None
        s = load_settings(); s.api.enabled = False; save_settings(s)
        self._refresh_status()
