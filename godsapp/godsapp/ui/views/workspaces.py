"""Workspaces view: list + create/edit/delete."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from godsapp.core import workspaces as ws_svc
from godsapp.ui.header_helpers import open_settings, page_header


class WorkspacesView(Gtk.Box):
    def __init__(self, parent) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(20); self.set_margin_bottom(20)
        self.set_margin_start(20); self.set_margin_end(20)
        self._parent = parent

        new_btn = Gtk.Button(label="New workspace")
        new_btn.add_css_class("suggested-action")
        new_btn.connect("clicked", lambda *_: self._open_editor(None))
        self.append(page_header(
            "Workspaces",
            on_settings=lambda: open_settings(parent),
            trailing=[new_btn],
            subtitle="Group scans, findings and evidence by engagement.",
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

        rows = ws_svc.list_workspaces()
        if not rows:
            empty = Adw.ActionRow(title="No workspaces yet",
                                  subtitle="Create one to organise scans and evidence.")
            self._list_box.append(empty)
            return

        for ws in rows:
            row = Adw.ActionRow(title=ws.name, subtitle=ws.description or ws.target or "")
            edit = Gtk.Button.new_from_icon_name("document-edit-symbolic")
            edit.add_css_class("flat")
            edit.connect("clicked", lambda _b, w=ws: self._open_editor(w))
            delete = Gtk.Button.new_from_icon_name("user-trash-symbolic")
            delete.add_css_class("flat")
            delete.connect("clicked", lambda _b, w=ws: self._confirm_delete(w))
            row.add_suffix(edit); row.add_suffix(delete)
            self._list_box.append(row)

    def _open_editor(self, ws) -> None:
        dialog = Adw.MessageDialog(
            transient_for=self._parent,
            heading="New workspace" if ws is None else f"Edit “{ws.name}”",
        )
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        name = Gtk.Entry(placeholder_text="Name")
        target = Gtk.Entry(placeholder_text="Primary target (optional)")
        desc = Gtk.Entry(placeholder_text="Description (optional)")
        if ws is not None:
            name.set_text(ws.name)
            target.set_text(ws.target or "")
            desc.set_text(ws.description or "")
        box.append(name); box.append(target); box.append(desc)
        dialog.set_extra_child(box)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("save")

        def on_response(_d, response: str) -> None:
            if response == "save":
                n = name.get_text().strip()
                if not n:
                    return
                if ws is None:
                    ws_svc.create_workspace(n, description=desc.get_text() or None,
                                            target=target.get_text() or None)
                else:
                    ws_svc.update_workspace(ws.id, name=n,
                                            description=desc.get_text() or None,
                                            target=target.get_text() or None)
                self.refresh()
        dialog.connect("response", on_response)
        dialog.present()

    def _confirm_delete(self, ws) -> None:
        dialog = Adw.MessageDialog(
            transient_for=self._parent,
            heading=f"Delete “{ws.name}”?",
            body="All scans, findings, and evidence associations will be removed. "
                 "Evidence files in the locker remain intact.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(_d, response: str) -> None:
            if response == "delete":
                ws_svc.delete_workspace(ws.id)
                self.refresh()
        dialog.connect("response", on_response)
        dialog.present()
