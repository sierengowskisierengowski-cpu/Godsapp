"""Evidence locker view."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from godsapp.core import evidence as ev_svc
from godsapp.ui.header_helpers import open_settings, page_header


class EvidenceView(Gtk.Box):
    def __init__(self, parent) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(20); self.set_margin_bottom(20)
        self.set_margin_start(20); self.set_margin_end(20)
        self._parent = parent

        ingest_btn = Gtk.Button(label="Ingest file")
        ingest_btn.add_css_class("suggested-action")
        ingest_btn.connect("clicked", lambda *_: self._pick_file())
        self.append(page_header(
            "Evidence Locker",
            on_settings=lambda: open_settings(parent),
            trailing=[ingest_btn],
            subtitle="Content-addressed by SHA-256. Every read/write/export is recorded in the chain of custody.",
        ))

        self._list_box = Gtk.ListBox()
        self._list_box.add_css_class("boxed-list")
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(self._list_box)
        self.append(scroll)

        self.refresh()

    def refresh(self) -> None:
        child = self._list_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._list_box.remove(child)
            child = nxt

        rows = ev_svc.list_evidence()
        if not rows:
            self._list_box.append(Adw.ActionRow(
                title="No evidence yet",
                subtitle="Click ‘Ingest file’ to add an artifact."))
            return

        for e in rows:
            row = Adw.ActionRow(
                title=e.filename,
                subtitle=f"{e.sha256[:16]}…  ·  {e.size_bytes:,} B  ·  {e.mime_type or '—'}",
            )
            verify_btn = Gtk.Button(label="Verify")
            verify_btn.add_css_class("flat")
            verify_btn.connect("clicked", lambda _b, ev=e: self._verify(ev))
            row.add_suffix(verify_btn)
            self._list_box.append(row)

    def _pick_file(self) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_title("Choose a file to ingest")

        def on_chosen(_d, result) -> None:
            try:
                file = dialog.open_finish(result)
            except Exception:
                return
            if file is None:
                return
            from pathlib import Path
            ev_svc.store_file(Path(file.get_path()), note="ingested via UI")
            self.refresh()

        dialog.open(self._parent, None, on_chosen)

    def _verify(self, ev) -> None:
        ok = ev_svc.verify(ev)
        toast = Adw.Toast(title=f"{ev.filename}: {'integrity OK' if ok else 'HASH MISMATCH'}")
        # Best-effort toast surfacing — main_window owns the toast overlay
        parent_toaster = getattr(self._parent, "_toast_overlay", None)
        if parent_toaster is not None:
            parent_toaster.add_toast(toast)
