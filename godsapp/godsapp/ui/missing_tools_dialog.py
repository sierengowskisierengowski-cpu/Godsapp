"""Missing Tools dialog — one-click install guidance + per-tool overrides.

Opened from:
- Dashboard system-status card ("Tools missing (N)" line, now clickable).
- ScanView header banner when the selected tool's binary is not installed.

Shows a grid of cards (one per missing tool). Each card expands to reveal:
- Auto-detected install command for the user's distro.
- "Install now" button (runs the command via ``pkexec`` when privilege
  escalation is required; runs in-process otherwise).
- "I have this installed" file picker → writes a per-tool override path
  to settings and re-runs detection on the spot.
- "Skip this tool" toggle → hides the tool from the missing counter.

Top of the dialog has an "Install all missing" button that batches every
selected tool's command per package manager and runs them sequentially
with a single privilege prompt per manager.

Author: Joseph Sierengowski.
"""
from __future__ import annotations

import subprocess
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from godsapp.core.logging import get_logger
from godsapp.core.settings import load_settings, save_settings
from godsapp.core.tool_catalog import (CATALOG, PKG_LABELS, PKG_MANAGERS,
                                       PKG_NEEDS_PRIV, CatalogEntry)
from godsapp.core.tool_detect import (Detection, detect_all, detect_one,
                                      detect_pkg_manager, install_cmd_for,
                                      test_binary)

log = get_logger(__name__)


_DIFF_BADGE_CLASS = {
    "beginner": "diff-beginner",
    "intermediate": "diff-intermediate",
    "expert": "diff-expert",
}


def _copy_to_clipboard(widget: Gtk.Widget, text: str) -> None:
    try:
        display = widget.get_display() or Gdk.Display.get_default()
        if display is not None:
            display.get_clipboard().set(text)
    except Exception:
        log.exception("clipboard copy failed")


class MissingToolsDialog(Adw.Window):
    """Modal dialog listing every missing tool with one-click install + override."""

    def __init__(self, parent: Optional[Gtk.Window] = None,
                 *, focus_tool_id: Optional[str] = None) -> None:
        super().__init__()
        self.set_title("Missing Tools")
        self.set_modal(True)
        if parent is not None:
            self.set_transient_for(parent)
        self.set_default_size(880, 720)
        self.add_css_class("missing-tools-dialog")

        self._focus_tool_id = focus_tool_id
        self._cards: dict[str, "_ToolCard"] = {}
        self._settings = load_settings()
        self._distro, self._pkg_mgr = detect_pkg_manager()
        self._detections: dict[str, Detection] = {}

        # Track in-flight subprocess pollers so we can stop them if the
        # dialog is closed mid-install (avoids the GLib.timeout_add callback
        # touching destroyed widgets).
        self._timeouts: set[int] = set()
        self._closed = False
        self.connect("close-request", self._on_close_request)

        # ── header ──────────────────────────────────────────────────────
        header = Adw.HeaderBar()
        self._refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        self._refresh_btn.set_tooltip_text("Re-run detection")
        self._refresh_btn.connect("clicked", lambda *_: self.refresh())
        header.pack_end(self._refresh_btn)

        # ── body ────────────────────────────────────────────────────────
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.append(header)

        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        top.set_margin_top(16); top.set_margin_bottom(8)
        top.set_margin_start(20); top.set_margin_end(20)
        self._title = Gtk.Label(xalign=0)
        self._title.add_css_class("title-1")
        self._subtitle = Gtk.Label(xalign=0)
        self._subtitle.add_css_class("dim-label")
        self._subtitle.set_wrap(True)
        top.append(self._title); top.append(self._subtitle)
        outer.append(top)

        # Install-all bar
        ia_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ia_bar.set_margin_start(20); ia_bar.set_margin_end(20)
        ia_bar.set_margin_bottom(8)
        self._install_all_btn = Gtk.Button(label="Install all missing")
        self._install_all_btn.add_css_class("suggested-action")
        self._install_all_btn.connect("clicked", lambda *_: self._install_all())
        ia_bar.append(self._install_all_btn)
        self._install_all_status = Gtk.Label(xalign=0)
        self._install_all_status.add_css_class("dim-label")
        self._install_all_status.set_hexpand(True)
        ia_bar.append(self._install_all_status)
        outer.append(ia_bar)

        # Scroll area with cards
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True); scroll.set_hexpand(True)
        self._cards_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._cards_box.set_margin_top(4); self._cards_box.set_margin_bottom(20)
        self._cards_box.set_margin_start(20); self._cards_box.set_margin_end(20)
        scroll.set_child(self._cards_box)
        outer.append(scroll)

        # Toast overlay so we can flash status messages
        self._toaster = Adw.ToastOverlay()
        self._toaster.set_child(outer)
        self.set_content(self._toaster)

        self.refresh()

    def _on_close_request(self, *_a) -> bool:
        self._closed = True
        for sid in list(self._timeouts):
            try:
                GLib.source_remove(sid)
            except Exception:
                pass
        self._timeouts.clear()
        return False

    def _track_timeout(self, ms: int, cb) -> int:
        sid_holder: dict[str, int] = {}
        def _wrapped():
            if self._closed:
                return False
            keep = cb()
            if not keep:
                self._timeouts.discard(sid_holder.get("sid", -1))
            return keep
        sid = GLib.timeout_add(ms, _wrapped)
        sid_holder["sid"] = sid
        self._timeouts.add(sid)
        return sid

    # ── refresh ─────────────────────────────────────────────────────────
    def refresh(self) -> None:
        self._settings = load_settings()
        self._detections = detect_all(overrides=dict(self._settings.tool_paths.overrides))
        skipped = set(self._settings.tool_paths.skipped)

        missing_ids = [tid for tid, d in self._detections.items()
                       if not d.found and tid not in skipped]
        skipped_missing = [tid for tid, d in self._detections.items()
                           if not d.found and tid in skipped]

        self._title.set_text(
            f"{len(missing_ids)} tool{'' if len(missing_ids)==1 else 's'} missing"
            if missing_ids else "All tools detected"
        )
        sub = (f"Detected distro: <b>{GLib.markup_escape_text(self._distro)}</b> "
               f"·  package manager: <b>{self._pkg_mgr}</b>")
        if skipped_missing:
            sub += f"  ·  hiding {len(skipped_missing)} skipped"
        self._subtitle.set_markup(sub)

        # Rebuild cards
        child = self._cards_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._cards_box.remove(child); child = nxt
        self._cards.clear()

        # Surface missing first, then skipped (collapsed), then installed.
        order = (missing_ids
                 + sorted(skipped_missing)
                 + sorted(tid for tid, d in self._detections.items() if d.found))
        for tid in order:
            entry = CATALOG.get(tid)
            if entry is None:
                continue
            det = self._detections[tid]
            card = _ToolCard(self, entry, det, self._pkg_mgr,
                             is_skipped=tid in skipped)
            self._cards_box.append(card)
            self._cards[tid] = card
            if self._focus_tool_id and tid == self._focus_tool_id:
                # Pop the focused tool's expander open on first render.
                GLib.idle_add(card.expand)

        self._install_all_btn.set_sensitive(bool(missing_ids))
        self._install_all_status.set_text("")

    # ── install all batcher ─────────────────────────────────────────────
    def _install_all(self) -> None:
        # Group commands by package manager so we issue one pkexec prompt
        # per manager (apt + pacman would be unusual but possible if the
        # user has mixed install paths).
        skipped = set(self._settings.tool_paths.skipped)
        batches: dict[str, list[tuple[str, str]]] = {}
        for tid, det in self._detections.items():
            if det.found or tid in skipped:
                continue
            entry = CATALOG.get(tid)
            if entry is None:
                continue
            cmd = install_cmd_for(entry, self._pkg_mgr)
            if not cmd:
                continue
            mgr = self._pkg_mgr if self._pkg_mgr in entry.install else next(
                (k for k in ("pipx", "pip", "brew", "go") if k in entry.install),
                self._pkg_mgr,
            )
            batches.setdefault(mgr, []).append((tid, cmd))

        if not batches:
            self._install_all_status.set_text("No install commands available.")
            return

        self._install_all_btn.set_sensitive(False)
        self._install_all_status.set_text("starting…")

        # Run sequentially so we get a single pkexec prompt per manager.
        self._run_batches(list(batches.items()), idx=0,
                          successes=[], failures=[])

    def _run_batches(self, batches, idx, successes, failures):
        if idx >= len(batches):
            msg = f"installed {len(successes)} · failed {len(failures)}"
            if failures:
                msg += "  — " + ", ".join(t for t, _ in failures[:6])
            self._install_all_status.set_text(msg)
            self._install_all_btn.set_sensitive(True)
            self._toaster.add_toast(Adw.Toast(title=msg, timeout=4))
            self.refresh()
            return
        mgr, items = batches[idx]
        joined = " && ".join(c for _, c in items)
        needs_priv = PKG_NEEDS_PRIV.get(mgr, True)
        if needs_priv:
            import shutil as _sh
            if _sh.which("pkexec") is None:
                # Privilege escalation unavailable — record failures for
                # the whole batch and move on.
                for tid, _ in items:
                    failures.append((tid, "pkexec missing"))
                self._run_batches(batches, idx+1, successes, failures)
                return
            cmd = ["pkexec", "sh", "-c", joined]
        else:
            cmd = ["sh", "-c", joined]
        self._install_all_status.set_text(
            f"installing {len(items)} via {mgr} ({idx+1}/{len(batches)})…"
        )
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except Exception as e:
            for tid, _ in items:
                failures.append((tid, str(e)))
            self._run_batches(batches, idx+1, successes, failures)
            return

        def _watch():
            rc = proc.poll()
            if rc is None:
                return True
            if rc == 0:
                for tid, _ in items:
                    successes.append(tid)
            else:
                for tid, _ in items:
                    failures.append((tid, f"exit {rc}"))
            self._run_batches(batches, idx+1, successes, failures)
            return False
        self._track_timeout(400, _watch)

    # ── per-card callbacks ──────────────────────────────────────────────
    def on_install(self, entry: CatalogEntry, cmd: str, btn: Gtk.Button) -> None:
        import shutil as _sh
        needs_priv = PKG_NEEDS_PRIV.get(self._pkg_mgr, True)
        if needs_priv and _sh.which("pkexec") is None:
            self._toaster.add_toast(Adw.Toast(
                title=f"pkexec missing — run manually: {cmd}", timeout=6))
            return
        btn.set_sensitive(False); btn.set_label("installing…")
        argv = (["pkexec", "sh", "-c", cmd] if needs_priv
                else ["sh", "-c", cmd])
        try:
            proc = subprocess.Popen(
                argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except Exception as e:
            btn.set_label(f"failed: {e}")
            return

        def _watch():
            rc = proc.poll()
            if rc is None:
                return True
            if rc == 0:
                btn.set_label("installed ✓")
            else:
                btn.set_label(f"failed (exit {rc})")
            # Re-detect just this tool and update its card without losing
            # the other cards' expansion state.
            det = detect_one(
                entry.tool_id,
                overrides=dict(load_settings().tool_paths.overrides),
            )
            self._detections[entry.tool_id] = det
            card = self._cards.get(entry.tool_id)
            if card is not None:
                card.update_detection(det)
            self._toaster.add_toast(Adw.Toast(
                title=(f"{entry.title}: installed" if rc == 0
                       else f"{entry.title}: install failed (exit {rc})"),
                timeout=4))
            return False
        self._track_timeout(400, _watch)

    def on_pick_override(self, entry: CatalogEntry) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_title(f"Locate {entry.title} binary")
        def _cb(d, res):
            try:
                f = d.open_finish(res)
            except Exception:
                return
            if f is None:
                return
            path = f.get_path()
            if not path:
                return
            s = load_settings()
            s.tool_paths.overrides[entry.tool_id] = path
            save_settings(s)
            det = detect_one(
                entry.tool_id,
                overrides=dict(s.tool_paths.overrides),
            )
            self._detections[entry.tool_id] = det
            card = self._cards.get(entry.tool_id)
            if card is not None:
                card.update_detection(det)
            self._toaster.add_toast(Adw.Toast(
                title=(f"{entry.title}: override saved → {path}" if det.found
                       else f"{entry.title}: {path} is not executable"),
                timeout=4))
        dialog.open(self, None, _cb)

    def on_skip(self, entry: CatalogEntry, skip: bool) -> None:
        s = load_settings()
        skipped = set(s.tool_paths.skipped)
        if skip:
            skipped.add(entry.tool_id)
        else:
            skipped.discard(entry.tool_id)
        s.tool_paths.skipped = sorted(skipped)
        save_settings(s)
        self._toaster.add_toast(Adw.Toast(
            title=f"{entry.title}: {'hidden from counter' if skip else 'unskipped'}",
            timeout=2))


# ────────────────────────────────────────────────────────────────────────
class _ToolCard(Gtk.Box):
    """One row per tool. Collapsed = header only; expanded shows full UX."""

    def __init__(self, dialog: MissingToolsDialog, entry: CatalogEntry,
                 detection: Detection, pkg_mgr: str, *,
                 is_skipped: bool) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("tool-card")
        self._dialog = dialog
        self._entry = entry
        self._det = detection
        self._pkg_mgr = pkg_mgr
        self._is_skipped = is_skipped
        self._expanded = False

        # ── header row ──────────────────────────────────────────────────
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.set_margin_top(10); header.set_margin_bottom(10)
        header.set_margin_start(14); header.set_margin_end(14)
        self._header = header

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_lbl = Gtk.Label(label=entry.title, xalign=0)
        title_lbl.add_css_class("tool-card-title")
        title_box.append(title_lbl)
        desc_lbl = Gtk.Label(label=entry.description, xalign=0)
        desc_lbl.add_css_class("dim-label"); desc_lbl.set_wrap(True)
        title_box.append(desc_lbl)
        title_box.set_hexpand(True)
        header.append(title_box)

        # Badges
        for label, css in (
            (entry.category.title(), "badge-cat"),
            (entry.difficulty.title(), _DIFF_BADGE_CLASS.get(entry.difficulty, "diff-intermediate")),
        ):
            b = Gtk.Label(label=label); b.add_css_class("tool-badge"); b.add_css_class(css)
            header.append(b)

        self._status_badge = Gtk.Label()
        self._status_badge.add_css_class("tool-badge")
        header.append(self._status_badge)

        self._expand_btn = Gtk.Button.new_from_icon_name("pan-end-symbolic")
        self._expand_btn.add_css_class("flat")
        self._expand_btn.connect("clicked", lambda *_: self.toggle())
        header.append(self._expand_btn)
        self.append(header)

        # Click-anywhere-on-header to toggle
        click = Gtk.GestureClick()
        click.connect("released", lambda *_: self.toggle())
        title_box.add_controller(click)

        # ── expanded body (built lazily) ────────────────────────────────
        self._body: Optional[Gtk.Widget] = None
        self._refresh_status_badge()

    def _refresh_status_badge(self) -> None:
        if self._det.found:
            self._status_badge.set_text(
                "Override ✓" if self._det.via_override
                else "Found ✓"
            )
            for c in ("status-missing", "status-skipped"):
                self._status_badge.remove_css_class(c)
            self._status_badge.add_css_class("status-found")
        elif self._is_skipped:
            self._status_badge.set_text("Skipped")
            for c in ("status-missing", "status-found"):
                self._status_badge.remove_css_class(c)
            self._status_badge.add_css_class("status-skipped")
        else:
            self._status_badge.set_text("Missing ✗")
            for c in ("status-found", "status-skipped"):
                self._status_badge.remove_css_class(c)
            self._status_badge.add_css_class("status-missing")

    def update_detection(self, det: Detection) -> None:
        self._det = det
        self._refresh_status_badge()
        if self._body is not None and self._expanded:
            # Rebuild body so the new path / install state shows.
            self.remove(self._body)
            self._body = self._build_body()
            self.append(self._body)

    # ── expand/collapse ─────────────────────────────────────────────────
    def expand(self) -> bool:
        if not self._expanded:
            self.toggle()
        return False

    def toggle(self) -> None:
        if self._expanded:
            if self._body is not None:
                self.remove(self._body)
                self._body = None
            self._expand_btn.set_icon_name("pan-end-symbolic")
            self._expanded = False
            return
        self._body = self._build_body()
        self.append(self._body)
        self._expand_btn.set_icon_name("pan-down-symbolic")
        self._expanded = True

    # ── body ────────────────────────────────────────────────────────────
    def _build_body(self) -> Gtk.Widget:
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        body.set_margin_start(14); body.set_margin_end(14)
        body.set_margin_top(0); body.set_margin_bottom(14)
        body.add_css_class("tool-card-body")

        # Detection summary
        if self._det.found:
            detail = (f"Detected at <tt>{GLib.markup_escape_text(self._det.path or '')}</tt>"
                      f"  (matched: <b>{GLib.markup_escape_text(self._det.binary or '?')}</b>)")
            if self._det.via_override:
                detail += "  ·  using your override"
            elif self._det.via_extra_dir:
                detail += "  ·  outside $PATH"
            lbl = Gtk.Label(xalign=0); lbl.set_markup(detail); lbl.set_wrap(True)
            body.append(lbl)
            test_row = Gtk.Box(spacing=8)
            test_btn = Gtk.Button(label="Test")
            test_btn.connect("clicked", lambda *_, p=self._det.path:
                             self._on_test(p, test_status))
            test_status = Gtk.Label(xalign=0); test_status.add_css_class("dim-label")
            test_status.set_hexpand(True)
            test_row.append(test_btn); test_row.append(test_status)
            body.append(test_row)
        else:
            why = Gtk.Label(xalign=0); why.set_wrap(True)
            why.set_markup(
                f"<b>Why is this missing?</b> {GLib.markup_escape_text(self._entry.description)}\n"
                f"<b>Unlocks:</b> "
                + GLib.markup_escape_text(", ".join(self._entry.unlocks) or "—")
            )
            body.append(why)

            if self._entry.alternatives:
                alts = ", ".join(self._entry.alternatives)
                body.append(self._labeled("Alternative tools", alts))

            if self._entry.notes:
                note = Gtk.Label(xalign=0); note.set_wrap(True)
                note.add_css_class("dim-label")
                note.set_markup("<i>" + GLib.markup_escape_text(self._entry.notes) + "</i>")
                body.append(note)

            # Install command for THIS distro first, all others below
            primary_cmd = install_cmd_for(self._entry, self._pkg_mgr)
            if primary_cmd is None:
                body.append(Gtk.Label(
                    label="No install command known for your package manager.",
                    xalign=0))
            else:
                body.append(self._build_install_row(self._pkg_mgr, primary_cmd,
                                                    primary=True))

            # Alt managers (collapsed expander)
            other = [(m, c) for m, c in self._entry.install.items()
                     if m != self._pkg_mgr]
            if other:
                exp = Gtk.Expander(label="Other package managers")
                ebox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                for m, c in sorted(other, key=lambda x: PKG_MANAGERS.index(x[0])
                                   if x[0] in PKG_MANAGERS else 99):
                    ebox.append(self._build_install_row(m, c, primary=False))
                exp.set_child(ebox)
                body.append(exp)

        # Override + skip row (always visible)
        ctrls = Gtk.Box(spacing=8)
        ctrls.set_margin_top(8)
        pick_btn = Gtk.Button(label="I have this installed…")
        pick_btn.connect("clicked", lambda *_:
                         self._dialog.on_pick_override(self._entry))
        ctrls.append(pick_btn)

        skip_tb = Gtk.ToggleButton(label=("Unskip" if self._is_skipped else "Skip this tool"))
        skip_tb.set_active(self._is_skipped)
        def _on_skip(b):
            self._is_skipped = b.get_active()
            self._dialog.on_skip(self._entry, self._is_skipped)
            b.set_label("Unskip" if self._is_skipped else "Skip this tool")
            self._refresh_status_badge()
        skip_tb.connect("toggled", _on_skip)
        ctrls.append(skip_tb)
        body.append(ctrls)

        return body

    def _build_install_row(self, mgr: str, cmd: str, *, primary: bool) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        row.add_css_class("install-row")
        header = Gtk.Box(spacing=8)
        label = Gtk.Label(xalign=0)
        label.set_markup(
            f"<b>{GLib.markup_escape_text(PKG_LABELS.get(mgr, mgr))}</b>  "
            f"<span weight='light'>({mgr})</span>"
        )
        label.set_hexpand(True)
        header.append(label)

        copy_btn = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
        copy_btn.add_css_class("flat")
        copy_btn.set_tooltip_text("Copy install command")
        copy_btn.connect("clicked", lambda b, c=cmd: (
            _copy_to_clipboard(b, c),
            self._dialog._toaster.add_toast(Adw.Toast(title="copied", timeout=2)),
        ))
        header.append(copy_btn)

        if primary:
            install_btn = Gtk.Button(label="Install now")
            install_btn.add_css_class("suggested-action")
            install_btn.connect("clicked", lambda b, e=self._entry, c=cmd:
                                self._dialog.on_install(e, c, b))
            header.append(install_btn)
        row.append(header)

        cmd_lbl = Gtk.Label(xalign=0)
        cmd_lbl.add_css_class("install-cmd")
        cmd_lbl.set_selectable(True)
        # Show command with sudo when privilege is required, for honesty.
        shown = (f"sudo {cmd}" if PKG_NEEDS_PRIV.get(mgr, True) else cmd)
        cmd_lbl.set_markup(f"<tt>{GLib.markup_escape_text(shown)}</tt>")
        cmd_lbl.set_wrap(True)
        row.append(cmd_lbl)
        return row

    def _labeled(self, label: str, text: str) -> Gtk.Widget:
        l = Gtk.Label(xalign=0); l.set_wrap(True)
        l.set_markup(f"<b>{GLib.markup_escape_text(label)}:</b> "
                     f"{GLib.markup_escape_text(text)}")
        return l

    def _on_test(self, path: str, status_lbl: Gtk.Label) -> None:
        status_lbl.set_text("testing…")
        def _do():
            ok, line = test_binary(path)
            status_lbl.set_text(("✓ " if ok else "✗ ") + line[:160])
            return False
        GLib.idle_add(_do)
