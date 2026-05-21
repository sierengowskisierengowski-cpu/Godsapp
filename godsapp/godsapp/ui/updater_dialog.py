"""Updater dialog — surfaces ``UpdateInfo`` and runs the install.

Author: Joseph Sierengowski.
"""
from __future__ import annotations

import threading
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from godsapp import __version__
from godsapp.core import updater as updater_core
from godsapp.core.logging import get_logger
from godsapp.core.settings import load_settings, save_settings

log = get_logger(__name__)


def _fmt_bytes(n: int) -> str:
    n = max(0, n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0
    return f"{n:.1f} TB"


class UpdaterDialog(Adw.Window):
    """Two-state window. Initial: "Check for updates" button. After a
    successful check that finds something: release notes + Install /
    Skip / Cancel.
    """

    def __init__(self, parent: Optional[Gtk.Window] = None,
                 *, preloaded: Optional[updater_core.CheckResult] = None) -> None:
        super().__init__()
        self.set_title("GodsApp updates")
        if parent is not None:
            self.set_transient_for(parent)
            self.set_modal(True)
        self.set_default_size(640, 540)
        self.add_css_class("updater-dialog")

        self._result: Optional[updater_core.CheckResult] = preloaded
        self._install: Optional[updater_core.InstallProcess] = None
        self._poll_source: Optional[int] = None
        self._closed = False
        self.connect("close-request", self._on_close_request)

        header = Adw.HeaderBar()
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)

        self._toaster = Adw.ToastOverlay()
        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._content_box.set_margin_top(18)
        self._content_box.set_margin_bottom(18)
        self._content_box.set_margin_start(18)
        self._content_box.set_margin_end(18)
        self._toaster.set_child(self._content_box)
        toolbar.set_content(self._toaster)
        self.set_content(toolbar)

        if self._result is not None:
            self._render_result(self._result)
        else:
            self._render_idle()

    # ── lifecycle ──────────────────────────────────────────────────────
    def _on_close_request(self, *_a) -> bool:
        self._closed = True
        if self._poll_source is not None:
            try:
                GLib.source_remove(self._poll_source)
            except Exception:
                pass
            self._poll_source = None
        if self._install is not None:
            self._install.cancel()
        return False

    def _clear(self) -> None:
        child = self._content_box.get_first_child()
        while child is not None:
            self._content_box.remove(child)
            child = self._content_box.get_first_child()

    # ── idle state ─────────────────────────────────────────────────────
    def _render_idle(self) -> None:
        self._clear()
        title = Gtk.Label(label="Check for GodsApp updates", xalign=0)
        title.add_css_class("title-2")
        self._content_box.append(title)

        sub = Gtk.Label(xalign=0, wrap=True)
        sub.set_markup(
            f"You're on <b>v{__version__}</b>.\n"
            "Click below to fetch the latest release from GitHub."
        )
        sub.add_css_class("dim-label")
        self._content_box.append(sub)

        actions = Gtk.Box(spacing=10, halign=Gtk.Align.END)
        check_btn = Gtk.Button(label="Check now")
        check_btn.add_css_class("suggested-action")
        check_btn.connect("clicked", lambda *_: self._do_check())
        actions.append(check_btn)
        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", lambda *_: self.close())
        actions.append(close_btn)
        self._content_box.append(actions)

        self._status = Gtk.Label(xalign=0); self._status.add_css_class("dim-label")
        self._content_box.append(self._status)

    def _do_check(self) -> None:
        self._status.set_text("Checking…")

        def _worker() -> None:
            result = updater_core.check_for_update()
            GLib.idle_add(self._on_check_result, result)

        threading.Thread(target=_worker, daemon=True, name="godsapp-updater").start()

    def _on_check_result(self, result: updater_core.CheckResult) -> bool:
        if self._closed:
            return False
        self._result = result
        self._render_result(result)
        return False

    # ── result state ───────────────────────────────────────────────────
    def _render_result(self, result: updater_core.CheckResult) -> None:
        self._clear()
        if result.error:
            self._render_error(result.error)
            return
        if result.info is None:
            self._render_up_to_date()
            return
        self._render_update_available(result.info)

    def _render_error(self, err: str) -> None:
        title = Gtk.Label(label="Couldn't check for updates", xalign=0)
        title.add_css_class("title-2")
        self._content_box.append(title)
        body = Gtk.Label(label=err, xalign=0, wrap=True)
        body.add_css_class("dim-label")
        self._content_box.append(body)
        actions = Gtk.Box(spacing=10, halign=Gtk.Align.END)
        retry = Gtk.Button(label="Try again")
        retry.connect("clicked", lambda *_: (self._render_idle(), self._do_check()))
        actions.append(retry)
        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", lambda *_: self.close())
        actions.append(close_btn)
        self._content_box.append(actions)

    def _render_up_to_date(self) -> None:
        title = Gtk.Label(label=f"You're on the latest version (v{__version__}).",
                          xalign=0)
        title.add_css_class("title-2")
        self._content_box.append(title)
        sub = Gtk.Label(
            label="No newer release is available on the configured channel.",
            xalign=0, wrap=True,
        )
        sub.add_css_class("dim-label")
        self._content_box.append(sub)
        actions = Gtk.Box(spacing=10, halign=Gtk.Align.END)
        re_btn = Gtk.Button(label="Check again")
        re_btn.connect("clicked", lambda *_: (self._render_idle(), self._do_check()))
        actions.append(re_btn)
        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", lambda *_: self.close())
        actions.append(close_btn)
        self._content_box.append(actions)

    def _render_update_available(self, info: updater_core.UpdateInfo) -> None:
        title = Gtk.Label(xalign=0)
        title.set_markup(
            f"<b>GodsApp v{info.version}</b> is available "
            f"<span size='small' alpha='65535'>(you're on v{__version__})</span>"
        )
        title.add_css_class("title-2")
        self._content_box.append(title)

        meta = Gtk.Label(xalign=0)
        bits = [info.name]
        if info.published_at:
            bits.append(f"published {info.published_at.split('T')[0]}")
        if info.asset_size:
            bits.append(f"download ≈ {_fmt_bytes(info.asset_size)}")
        if info.prerelease:
            bits.append("pre-release")
        meta.set_text("  ·  ".join(bits))
        meta.add_css_class("dim-label")
        self._content_box.append(meta)

        # Notes (scrollable)
        notes_view = Gtk.TextView()
        notes_view.set_editable(False)
        notes_view.set_cursor_visible(False)
        notes_view.set_wrap_mode(Gtk.WrapMode.WORD)
        notes_view.set_monospace(False)
        notes_view.get_buffer().set_text(info.notes or "(no release notes)")
        notes_view.set_top_margin(8); notes_view.set_bottom_margin(8)
        notes_view.set_left_margin(8); notes_view.set_right_margin(8)
        scroll = Gtk.ScrolledWindow()
        scroll.set_hexpand(True); scroll.set_vexpand(True)
        scroll.set_min_content_height(180)
        scroll.set_child(notes_view)
        scroll.add_css_class("card")
        self._content_box.append(scroll)

        self._progress = Gtk.ProgressBar()
        self._progress.set_show_text(True)
        self._progress.set_text("")
        self._progress.set_visible(False)
        self._content_box.append(self._progress)

        self._stage_lbl = Gtk.Label(xalign=0); self._stage_lbl.add_css_class("dim-label")
        self._content_box.append(self._stage_lbl)

        # Action bar
        actions = Gtk.Box(spacing=10, halign=Gtk.Align.END)
        skip_btn = Gtk.Button(label="Skip this version")
        skip_btn.connect("clicked", lambda *_: self._on_skip(info))
        actions.append(skip_btn)
        later_btn = Gtk.Button(label="Remind me later")
        later_btn.connect("clicked", lambda *_: self.close())
        actions.append(later_btn)
        self._install_btn = Gtk.Button(label="Download and install")
        self._install_btn.add_css_class("suggested-action")
        self._install_btn.connect("clicked", lambda *_: self._on_install(info))
        actions.append(self._install_btn)
        self._content_box.append(actions)

    def _on_skip(self, info: updater_core.UpdateInfo) -> None:
        try:
            s = load_settings()
            s.updates.skipped_version = info.version
            save_settings(s)
        except Exception:
            log.exception("failed to persist skipped_version")
        self._toaster.add_toast(Adw.Toast(title=f"v{info.version} skipped"))
        self.close()

    def _on_install(self, info: updater_core.UpdateInfo) -> None:
        self._install_btn.set_sensitive(False)
        self._progress.set_visible(True)
        user_scope = load_settings().updates.user_scope

        def _progress_cb(p: updater_core._Progress) -> None:
            def _apply() -> bool:
                if self._closed:
                    return False
                self._stage_lbl.set_text(p.message or p.stage)
                if p.bytes_total > 0:
                    frac = max(0.0, min(1.0, p.bytes_done / p.bytes_total))
                    self._progress.set_fraction(frac)
                    self._progress.set_text(
                        f"{_fmt_bytes(p.bytes_done)} / {_fmt_bytes(p.bytes_total)}"
                    )
                else:
                    self._progress.pulse()
                return False
            GLib.idle_add(_apply)

        def _worker() -> None:
            try:
                inst = updater_core.download_and_install(
                    info, user_scope=user_scope, progress_cb=_progress_cb,
                )
                GLib.idle_add(self._on_install_launched, inst)
            except Exception as e:
                log.exception("install failed")
                GLib.idle_add(self._on_install_failed, str(e))

        threading.Thread(target=_worker, daemon=True,
                         name="godsapp-updater-install").start()

    def _on_install_launched(self, inst: updater_core.InstallProcess) -> bool:
        if self._closed:
            inst.cancel()
            return False
        self._install = inst
        self._stage_lbl.set_text("Running install.sh…")
        self._progress.set_fraction(0.0)
        self._progress.set_text("installing")

        def _tick() -> bool:
            if self._closed or self._install is None:
                return False
            rc = self._install.poll()
            self._progress.pulse()
            if rc is None:
                return True
            self._poll_source = None
            if rc == 0:
                self._progress.set_fraction(1.0)
                self._progress.set_text("done")
                self._stage_lbl.set_text(
                    "Install complete. Quit and relaunch GodsApp to use the new version."
                )
                self._toaster.add_toast(
                    Adw.Toast(title="Update installed — relaunch to use it")
                )
            else:
                self._stage_lbl.set_text(
                    f"Install failed (exit {rc}). See log:\n{self._install.log_path}"
                )
                self._toaster.add_toast(Adw.Toast(title=f"Update failed (rc={rc})"))
                self._install_btn.set_sensitive(True)
            return False

        self._poll_source = GLib.timeout_add(500, _tick)
        return False

    def _on_install_failed(self, msg: str) -> bool:
        if self._closed:
            return False
        self._install_btn.set_sensitive(True)
        self._stage_lbl.set_text(f"Failed: {msg}")
        self._toaster.add_toast(Adw.Toast(title="Update failed"))
        return False


# ── background-launch helper ──────────────────────────────────────────────
def show_updater(parent: Optional[Gtk.Window],
                 preloaded: Optional[updater_core.CheckResult] = None) -> UpdaterDialog:
    dlg = UpdaterDialog(parent, preloaded=preloaded)
    dlg.present()
    return dlg
