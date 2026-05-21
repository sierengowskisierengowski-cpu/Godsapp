"""Themed login gate — shown between the splash and the main window.

First launch: prompts to set a password (with confirm field).
Subsequent launches: prompts for the existing password.
Credentials live in ~/.config/godsapp/settings.toml under [login].

Author: Joseph Sierengowski.
"""
from __future__ import annotations

import hashlib
import os
import secrets

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from godsapp import __app_name__, __version__
from godsapp.core.audio import play_async
from godsapp.core.logging import get_logger
from godsapp.core.settings import load_settings, save_settings

log = get_logger(__name__)


def _hash(salt: str, password: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


class LoginWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, *, on_success) -> None:
        super().__init__(application=app, title=f"{__app_name__} · Enter the Realm")
        self.set_default_size(520, 600)
        self.set_resizable(False)
        self.add_css_class("godsapp-window")
        self.add_css_class("login-window")
        self._on_success = on_success
        self._settings = load_settings()
        self._is_setup = not (self._settings.login.pwhash and self._settings.login.salt)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        header.set_title_widget(Gtk.Label(label=""))
        toolbar.add_top_bar(header)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        body.set_margin_top(20); body.set_margin_bottom(40)
        body.set_margin_start(48); body.set_margin_end(48)
        body.set_halign(Gtk.Align.FILL); body.set_valign(Gtk.Align.CENTER)
        body.set_hexpand(True); body.set_vexpand(True)

        # Logo
        try:
            from importlib.resources import files
            svg_path = files("godsapp.resources.icons").joinpath("godsapp-logo.svg")
            logo = Gtk.Image.new_from_file(str(svg_path))
            logo.set_pixel_size(120); logo.add_css_class("login-logo")
        except Exception:
            logo = Gtk.Label(label="☁⚡"); logo.add_css_class("login-logo-fallback")
        logo.set_halign(Gtk.Align.CENTER)
        body.append(logo)

        title = Gtk.Label(label="ENTER THE REALM")
        title.add_css_class("login-title"); title.set_halign(Gtk.Align.CENTER)
        sub = Gtk.Label(label="Mount Olympus awaits" if not self._is_setup
                              else "Forge your first key to the realm")
        sub.add_css_class("login-sub"); sub.set_halign(Gtk.Align.CENTER)
        body.append(title); body.append(sub)

        # Fields
        group = Adw.PreferencesGroup()
        default_user = self._settings.login.user or os.environ.get("USER") or "demigod"
        self._user_row = Adw.EntryRow(title="Name")
        self._user_row.set_text(default_user)
        self._pw_row = Adw.PasswordEntryRow(title="Password")
        group.add(self._user_row)
        group.add(self._pw_row)
        if self._is_setup:
            self._pw2_row = Adw.PasswordEntryRow(title="Confirm password")
            group.add(self._pw2_row)
        else:
            self._pw2_row = None
        body.append(group)

        # Error label
        self._error_lbl = Gtk.Label(label="", xalign=0.5)
        self._error_lbl.add_css_class("login-error")
        body.append(self._error_lbl)

        # Buttons
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                          halign=Gtk.Align.CENTER)
        self._submit_btn = Gtk.Button(
            label=("FORGE KEY · ENTER" if self._is_setup else "ENTER")
        )
        self._submit_btn.add_css_class("suggested-action")
        self._submit_btn.add_css_class("login-submit")
        self._submit_btn.connect("clicked", lambda *_: self._submit())
        btn_row.append(self._submit_btn)
        body.append(btn_row)

        # Hint
        hint = Gtk.Label(label=f"GodsApp v{__version__} · Press Enter to proceed")
        hint.add_css_class("login-hint"); hint.set_halign(Gtk.Align.CENTER)
        body.append(hint)

        toolbar.set_content(body)
        self.set_content(toolbar)

        # Enter-key triggers submit
        key = Gtk.EventControllerKey.new()
        key.connect("key-pressed", self._on_key)
        self.add_controller(key)

        # Autofocus password field
        GLib.timeout_add(120, lambda: (self._pw_row.grab_focus(), False)[1])

    def _on_key(self, _ctrl, keyval, _kc, _state) -> bool:
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._submit()
            return True
        return False

    def _shake(self) -> None:
        self.add_css_class("login-shake")
        GLib.timeout_add(550, lambda: (self.remove_css_class("login-shake"), False)[1])
        try:
            play_async("thunder_crackle.wav")
        except Exception:
            pass

    def _set_error(self, msg: str) -> None:
        self._error_lbl.set_text(msg)
        if msg:
            self._shake()

    def _submit(self) -> None:
        user = self._user_row.get_text().strip() or "demigod"
        pw = self._pw_row.get_text()
        if not pw:
            self._set_error("A password is required to cross the gate.")
            return

        if self._is_setup:
            pw2 = self._pw2_row.get_text() if self._pw2_row else ""
            if pw != pw2:
                self._set_error("Passwords do not match.")
                return
            if len(pw) < 4:
                self._set_error("Forge something stronger — at least 4 characters.")
                return
            salt = secrets.token_hex(16)
            self._settings.login.user = user
            self._settings.login.salt = salt
            self._settings.login.pwhash = _hash(salt, pw)
            self._settings.login.enabled = True
            try:
                save_settings(self._settings)
            except Exception:
                log.exception("login: failed to save credentials")
                self._set_error("Could not save credentials — check write permissions.")
                return
            self._succeed()
            return

        # Verify existing credentials
        expected = self._settings.login.pwhash
        actual = _hash(self._settings.login.salt, pw)
        if actual != expected:
            self._set_error("The gate rejects you.")
            self._pw_row.set_text("")
            return
        self._succeed()

    def _succeed(self) -> None:
        try:
            play_async("thunder_close.wav")
        except Exception:
            pass
        try:
            self._on_success()
        finally:
            self.close()


def show_login(app: Adw.Application, *, on_success) -> LoginWindow | None:
    """Show the login window. If login is disabled in settings, call on_success directly."""
    s = load_settings()
    if not s.login.enabled:
        on_success()
        return None
    win = LoginWindow(app, on_success=on_success)
    win.present()
    return win
