"""Workspaces view: list + create/edit/delete."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from godsapp.core import workspaces as ws_svc
from godsapp.core.templates import TEMPLATES, get_template
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

        # Template picker (new workspaces only) ───────────────────────────
        template_dd = None
        template_hint = None
        if ws is None:
            template_dd = Gtk.DropDown.new_from_strings([t.title for t in TEMPLATES])
            template_dd.set_selected(0)
            template_hint = Gtk.Label(
                label=TEMPLATES[0].description, xalign=0)
            template_hint.add_css_class("dim-label")
            template_hint.set_wrap(True)
            tpl_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            tpl_row.append(Gtk.Label(label="Template:"))
            tpl_row.append(template_dd)
            box.append(tpl_row)
            box.append(template_hint)

        name = Gtk.Entry(placeholder_text="Name")
        target = Gtk.Entry(placeholder_text="Primary target (optional)")
        desc = Gtk.Entry(placeholder_text="Description (optional)")
        if ws is not None:
            name.set_text(ws.name)
            target.set_text(ws.target or "")
            desc.set_text(ws.description or "")
        box.append(name); box.append(target); box.append(desc)

        # Wire template selection — auto-fill empty fields
        if template_dd is not None and template_hint is not None:
            def _on_template_changed(*_a) -> None:
                idx = template_dd.get_selected()
                if 0 <= idx < len(TEMPLATES):
                    t = TEMPLATES[idx]
                    template_hint.set_text(t.description)
                    # Only auto-fill when the user hasn't typed anything yet.
                    if not target.get_text().strip() and t.default_target:
                        target.set_text(t.default_target)
                    if not desc.get_text().strip() and t.default_tags:
                        desc.set_text("tags: " + ", ".join(t.default_tags))
            template_dd.connect("notify::selected", _on_template_changed)

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
                    new_ws = ws_svc.create_workspace(
                        n, description=desc.get_text() or None,
                        target=target.get_text() or None)
                    # Apply template welcome note as a workspace README file
                    if template_dd is not None:
                        idx = template_dd.get_selected()
                        if 0 <= idx < len(TEMPLATES):
                            tpl = TEMPLATES[idx]
                            if tpl.welcome_note and new_ws is not None:
                                try:
                                    from godsapp.core import paths
                                    ws_dir = paths.WORKSPACE_DIR / new_ws.id
                                    ws_dir.mkdir(parents=True, exist_ok=True)
                                    (ws_dir / "README.md").write_text(
                                        tpl.welcome_note, encoding="utf-8")
                                except Exception:
                                    pass
                            toaster = getattr(self._parent, "_toast_overlay", None)
                            if toaster is not None:
                                toaster.add_toast(Adw.Toast(
                                    title=f"Workspace '{n}' created from {tpl.title}"))
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
