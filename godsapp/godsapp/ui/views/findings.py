"""Findings Manager — list, filter, and triage every finding across workspaces."""
from __future__ import annotations

from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from godsapp.db import Finding, Scan, Workspace, get_session
from godsapp.ui.header_helpers import open_settings, page_header

_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
_SEVERITIES = ["all", "critical", "high", "medium", "low", "info"]
_STATUSES = ["all", "open", "triaged", "confirmed", "fixed", "wontfix", "duplicate"]


class FindingsView(Gtk.Box):
    def __init__(self, parent) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_margin_top(20); self.set_margin_bottom(20)
        self.set_margin_start(20); self.set_margin_end(20)
        self._parent = parent
        self._rows_data: list[dict] = []

        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.add_css_class("flat")
        refresh_btn.connect("clicked", lambda *_: self.refresh())

        export_btn = Gtk.Button.new_from_icon_name("document-save-symbolic")
        export_btn.add_css_class("flat")
        export_btn.set_tooltip_text("Export filtered findings to CSV")
        export_btn.connect("clicked", lambda *_: self._export_csv())

        self.append(page_header(
            "Findings Manager",
            on_settings=lambda: open_settings(parent, "findings"),
            trailing=[export_btn, refresh_btn],
            subtitle="Every parsed finding across every scan. Filter, triage, and enrich with CVSS / CVE / MITRE.",
        ))

        # filter row
        flt = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._sev_dd = Gtk.DropDown.new_from_strings(_SEVERITIES)
        self._sev_dd.set_selected(0)
        self._sev_dd.connect("notify::selected", lambda *_: self._render())
        flt.append(Gtk.Label(label="Severity:"))
        flt.append(self._sev_dd)
        self._status_dd = Gtk.DropDown.new_from_strings(_STATUSES)
        self._status_dd.set_selected(0)
        self._status_dd.connect("notify::selected", lambda *_: self._render())
        flt.append(Gtk.Label(label="  Status:"))
        flt.append(self._status_dd)
        self._search = Gtk.SearchEntry()
        self._search.set_placeholder_text("search title / host / tool")
        self._search.set_hexpand(True)
        self._search.connect("search-changed", lambda *_: self._render())
        flt.append(self._search)
        self.append(flt)

        # counters
        self._counter_lbl = Gtk.Label(label="", xalign=0)
        self._counter_lbl.add_css_class("dim-label")
        self.append(self._counter_lbl)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list.add_css_class("boxed-list")
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True); scroll.set_child(self._list)
        self.append(scroll)

        self.refresh()

    # ── data ──────────────────────────────────────────────────────────────
    def refresh(self) -> None:
        with get_session() as s:
            rows = s.execute(
                select(Finding, Scan, Workspace)
                .join(Scan, Finding.scan_id == Scan.id)
                .join(Workspace, Scan.workspace_id == Workspace.id)
                .order_by(Finding.created_at.desc())
            ).all()
            data = []
            for f, sc, ws in rows:
                data.append({
                    "id": f.id, "title": f.title, "severity": f.severity,
                    "status": getattr(f, "status", None) or "open",
                    "host": f.host, "port": f.port, "service": f.service,
                    "tool": sc.tool, "category": sc.category,
                    "workspace": ws.name, "workspace_id": ws.id,
                    "cvss_score": getattr(f, "cvss_score", None),
                    "cve_ids": getattr(f, "cve_ids", None),
                    "mitre_technique": getattr(f, "mitre_technique", None),
                    "tags": getattr(f, "tags", None),
                    "description": f.description or "",
                    "created_at": f.created_at,
                })
        self._rows_data = data
        self._render()

    def _render(self) -> None:
        # clear
        child = self._list.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._list.remove(child)
            child = nxt
        sev = _SEVERITIES[self._sev_dd.get_selected()]
        st = _STATUSES[self._status_dd.get_selected()]
        q = (self._search.get_text() or "").lower().strip()
        shown = 0
        sev_totals = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for row in sorted(self._rows_data, key=lambda r: _SEV_ORDER.get(r["severity"], 9)):
            if sev != "all" and row["severity"] != sev:
                continue
            if st != "all" and row["status"] != st:
                continue
            if q:
                blob = " ".join(str(x) for x in (
                    row["title"], row["host"], row["tool"], row["workspace"],
                    row["cve_ids"] or "", row["tags"] or "")).lower()
                if q not in blob:
                    continue
            self._list.append(self._make_row(row))
            shown += 1
            sev_totals[row["severity"]] = sev_totals.get(row["severity"], 0) + 1
        if shown == 0:
            self._list.append(Adw.ActionRow(
                title="No findings match this filter.",
                subtitle="Run a scan from the sidebar to populate the catalogue."))
        total = len(self._rows_data)
        sev_bits = " · ".join(f"{k}: {sev_totals.get(k,0)}" for k in
                              ("critical", "high", "medium", "low", "info"))
        self._counter_lbl.set_text(f"{shown} shown / {total} total  ·  {sev_bits}")

    def _make_row(self, data: dict) -> Gtk.Widget:
        sev = data["severity"]
        subtitle = f"{data['tool']}  ·  {data['workspace']}  ·  {data['host'] or '—'}"
        if data.get("cvss_score") is not None:
            subtitle += f"  ·  CVSS {data['cvss_score']}"
        if data.get("cve_ids"):
            subtitle += f"  ·  CVE: {data['cve_ids']}"
        if data.get("mitre_technique"):
            subtitle += f"  ·  MITRE: {data['mitre_technique']}"
        row = Adw.ActionRow(title=data["title"], subtitle=subtitle)
        badge = Gtk.Label(label=sev.upper())
        badge.add_css_class("severity-badge"); badge.add_css_class(f"sev-{sev}")
        row.add_prefix(badge)
        status_lbl = Gtk.Label(label=data["status"])
        status_lbl.add_css_class("dim-label")
        edit_btn = Gtk.Button.new_from_icon_name("document-edit-symbolic")
        edit_btn.add_css_class("flat")
        edit_btn.connect("clicked", lambda *_: self._open_edit(data["id"]))
        row.add_suffix(status_lbl); row.add_suffix(edit_btn)
        return row

    # ── csv export ────────────────────────────────────────────────────────
    def _export_csv(self) -> None:
        """Write the currently-filtered finding list to a CSV in the user's
        evidence dir and surface a toast with the path."""
        import csv
        from datetime import datetime
        from godsapp.core import paths
        sev = _SEVERITIES[self._sev_dd.get_selected()]
        st = _STATUSES[self._status_dd.get_selected()]
        q = (self._search.get_text() or "").lower().strip()
        out_rows = []
        for row in sorted(self._rows_data, key=lambda r: _SEV_ORDER.get(r["severity"], 9)):
            if sev != "all" and row["severity"] != sev: continue
            if st != "all" and row["status"] != st: continue
            if q:
                blob = " ".join(str(x) for x in (
                    row["title"], row["host"], row["tool"], row["workspace"],
                    row["cve_ids"] or "", row["tags"] or "")).lower()
                if q not in blob: continue
            out_rows.append(row)
        out_dir = paths.EVIDENCE_DIR / "exports"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        out_path = out_dir / f"findings-{stamp}.csv"
        cols = ["created_at", "severity", "status", "workspace", "tool", "category",
                "host", "port", "service", "title", "cvss_score", "cve_ids",
                "mitre_technique", "tags", "description"]
        with out_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for r in out_rows:
                w.writerow([
                    r["created_at"].isoformat() if r["created_at"] else "",
                    r["severity"], r["status"], r["workspace"], r["tool"], r["category"],
                    r["host"] or "", r["port"] or "", r["service"] or "",
                    r["title"], r["cvss_score"] or "", r["cve_ids"] or "",
                    r["mitre_technique"] or "", r["tags"] or "",
                    (r["description"] or "").replace("\n", " ").strip(),
                ])
        toaster = getattr(self._parent, "_toast_overlay", None)
        msg = f"Exported {len(out_rows)} findings → {out_path}"
        if toaster is not None:
            toaster.add_toast(Adw.Toast(title=msg))
        if hasattr(self._parent, "_set_status_text"):
            self._parent._set_status_text(msg)

    # ── editor ────────────────────────────────────────────────────────────
    def _open_edit(self, finding_id: str) -> None:
        with get_session() as s:
            f = s.get(Finding, finding_id)
            if f is None:
                return
            current = {
                "title": f.title, "severity": f.severity,
                "status": getattr(f, "status", None) or "open",
                "cvss_score": getattr(f, "cvss_score", None),
                "cve_ids": getattr(f, "cve_ids", None) or "",
                "mitre_technique": getattr(f, "mitre_technique", None) or "",
                "tags": getattr(f, "tags", None) or "",
                "description": f.description or "",
            }
        dlg = Adw.Window(transient_for=self._parent, modal=True)
        dlg.set_title(f"Edit finding · {current['title'][:60]}")
        dlg.set_default_size(560, 560)
        tv = Adw.ToolbarView()
        hb = Adw.HeaderBar()
        btn_save = Gtk.Button(label="Save")
        btn_save.add_css_class("suggested-action")
        btn_del = Gtk.Button(label="Delete")
        btn_del.add_css_class("destructive-action")
        hb.pack_end(btn_save); hb.pack_start(btn_del)
        tv.add_top_bar(hb)
        page = Adw.PreferencesPage()
        g = Adw.PreferencesGroup(title="Triage")

        sev_dd = Adw.ComboRow(title="Severity")
        sev_choices = ["info", "low", "medium", "high", "critical"]
        sev_dd.set_model(Gtk.StringList.new(sev_choices))
        try:
            sev_dd.set_selected(sev_choices.index(current["severity"]))
        except ValueError:
            sev_dd.set_selected(0)
        g.add(sev_dd)

        status_dd = Adw.ComboRow(title="Status")
        status_choices = ["open", "triaged", "confirmed", "fixed", "wontfix", "duplicate"]
        status_dd.set_model(Gtk.StringList.new(status_choices))
        try:
            status_dd.set_selected(status_choices.index(current["status"]))
        except ValueError:
            status_dd.set_selected(0)
        g.add(status_dd)

        cvss = Adw.SpinRow.new_with_range(0.0, 10.0, 0.1)
        cvss.set_title("CVSS score")
        cvss.set_digits(1)
        if current["cvss_score"] is not None:
            try:
                cvss.set_value(float(current["cvss_score"]))
            except Exception:
                pass
        g.add(cvss)

        cve = Adw.EntryRow(title="CVE IDs (comma-separated)")
        cve.set_text(current["cve_ids"]); g.add(cve)
        mitre = Adw.EntryRow(title="MITRE ATT&CK technique (e.g. T1190)")
        mitre.set_text(current["mitre_technique"]); g.add(mitre)
        tags = Adw.EntryRow(title="Tags (comma-separated)")
        tags.set_text(current["tags"]); g.add(tags)
        page.add(g)

        notes_g = Adw.PreferencesGroup(title="Description / notes")
        notes_buf = Gtk.TextBuffer()
        notes_buf.set_text(current["description"])
        notes_view = Gtk.TextView.new_with_buffer(notes_buf)
        notes_view.set_wrap_mode(Gtk.WrapMode.WORD)
        notes_scroll = Gtk.ScrolledWindow()
        notes_scroll.set_min_content_height(160)
        notes_scroll.set_child(notes_view)
        notes_g.add(notes_scroll)
        page.add(notes_g)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True); scroll.set_child(page)
        tv.set_content(scroll)
        dlg.set_content(tv)

        def save_cb(*_a) -> None:
            new = {
                "severity": sev_choices[sev_dd.get_selected()],
                "status":   status_choices[status_dd.get_selected()],
                "cvss_score": cvss.get_value(),
                "cve_ids":  cve.get_text().strip() or None,
                "mitre_technique": mitre.get_text().strip() or None,
                "tags":     tags.get_text().strip() or None,
                "description": notes_buf.get_text(
                    notes_buf.get_start_iter(), notes_buf.get_end_iter(), False),
            }
            with get_session() as s:
                f = s.get(Finding, finding_id)
                if f is None:
                    return
                for k, v in new.items():
                    setattr(f, k, v)
            dlg.close()
            self.refresh()

        def del_cb(*_a) -> None:
            with get_session() as s:
                f = s.get(Finding, finding_id)
                if f is not None:
                    s.delete(f)
            dlg.close()
            self.refresh()

        btn_save.connect("clicked", save_cb)
        btn_del.connect("clicked", del_cb)
        dlg.present()
