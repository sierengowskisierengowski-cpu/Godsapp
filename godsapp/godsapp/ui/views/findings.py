"""Findings Manager — list, filter, and triage every finding across workspaces."""
from __future__ import annotations

from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from godsapp.core.dedup import find_duplicates
from godsapp.db import Finding, FindingLink, Scan, Workspace, get_session
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
        edit_btn.set_tooltip_text("Edit / triage this finding")
        edit_btn.connect("clicked", lambda *_: self._open_edit(data["id"]))
        link_btn = Gtk.Button.new_from_icon_name("emblem-shared-symbolic")
        link_btn.add_css_class("flat")
        link_btn.set_tooltip_text("Find duplicates or link related findings")
        link_btn.connect("clicked", lambda *_, d=data: self._open_link_dialog(d))
        row.add_suffix(status_lbl); row.add_suffix(link_btn); row.add_suffix(edit_btn)
        return row

    # ── dedup / link UI (v0.4.0) ──────────────────────────────────────────
    def _open_link_dialog(self, data: dict) -> None:
        """Show likely duplicates in the same workspace and let the user
        confirm a link (kind=duplicate / related / chain / supersedes)."""
        candidate = {
            "title":           data.get("title"),
            "host":            data.get("host"),
            "port":            data.get("port"),
            "cve_ids":         data.get("cve_ids"),
            "mitre_technique": data.get("mitre_technique"),
            "description":    data.get("description"),
        }
        # Settings: thresholds are stored as 0–100 ints; normalise to 0–1 here.
        # Accept legacy float values (≤1.0) defensively in case an old settings
        # file is loaded.
        def _to_fraction(v: float) -> float:
            v = float(v)
            if v > 1.0:
                v = v / 100.0
            return max(0.0, min(1.0, v))
        try:
            from godsapp.core.settings import load_settings
            ds = load_settings().dedup
            sugg = _to_fraction(ds.suggest_threshold)
            enabled = ds.enabled
        except Exception:
            sugg, enabled = 0.85, True
        # Always show the dialog when the user clicks Link, but warn the user
        # if dedup is globally disabled so they understand the suggestions are
        # read-only / no auto-merge will fire on save.
        try:
            # Show borderline candidates too: 0.20 below the suggestion
            # threshold. The score floor is intentionally not clamped — if the
            # user sets a high suggestion threshold (e.g. 95%), they probably
            # still want to see ~75% candidates here.
            view_threshold = max(0.0, sugg - 0.20)
            matches = find_duplicates(
                data["workspace_id"], candidate,
                threshold=view_threshold,
                exclude_finding_id=data["id"],
                limit=20,
            )
        except Exception:
            matches = []

        dlg = Adw.Window(transient_for=self._parent, modal=True)
        dlg.set_title(f"Link finding · {data['title'][:60]}")
        dlg.set_default_size(640, 480)
        tv = Adw.ToolbarView()
        hb = Adw.HeaderBar(); hb.add_css_class("flat")
        tv.add_top_bar(hb)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        body.set_margin_top(14); body.set_margin_bottom(14)
        body.set_margin_start(14); body.set_margin_end(14)

        if not enabled:
            warn = Gtk.Label(
                label="Dedup is disabled in Settings → Findings Dedup; "
                      "suggestions below are read-only previews.",
                xalign=0)
            warn.add_css_class("dim-label"); warn.set_wrap(True)
            body.append(warn)

        if not matches:
            body.append(Gtk.Label(
                label="No similar findings detected in this workspace.",
                xalign=0))
        else:
            sugg_pct = int(sugg * 100)
            note = Gtk.Label(
                label=f"Suggestion threshold: {sugg_pct}%  ·  "
                      f"matches above this score are likely duplicates.",
                xalign=0)
            note.add_css_class("dim-label")
            body.append(note)
            header = Gtk.Label(
                label=f"{len(matches)} potentially related finding(s) in this workspace:",
                xalign=0)
            header.add_css_class("dim-label")
            body.append(header)

            kind_dd = Gtk.DropDown.new_from_strings(
                ["duplicate", "related", "chain", "supersedes"])
            kind_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            kind_row.append(Gtk.Label(label="Link kind:"))
            kind_row.append(kind_dd)
            body.append(kind_row)

            # Existing finding row → score + reasons + Link button
            match_box = Gtk.ListBox()
            match_box.add_css_class("boxed-list")
            scroll = Gtk.ScrolledWindow()
            scroll.set_vexpand(True); scroll.set_child(match_box)
            body.append(scroll)

            # Pull titles for context (one extra query — small lists)
            try:
                with get_session() as s:
                    others = {
                        f.id: f for f in
                        s.query(Finding).filter(
                            Finding.id.in_([m.finding_id for m in matches])
                        ).all()
                    }
            except Exception:
                others = {}

            for m in matches:
                other = others.get(m.finding_id)
                title = other.title if other is not None else m.finding_id[:8]
                reason_str = " · ".join(m.reasons) if m.reasons else "weak signal"
                ar = Adw.ActionRow(
                    title=title,
                    subtitle=f"score {int(m.score * 100)}% · {reason_str}")
                link = Gtk.Button(label="Link")
                link.add_css_class("suggested-action")
                kind_dd_ref = kind_dd
                def _do_link(_b, fid=m.finding_id) -> None:
                    kind = ["duplicate", "related", "chain",
                            "supersedes"][kind_dd_ref.get_selected()]
                    self._create_link(data["id"], fid, kind)
                    dlg.close()
                link.connect("clicked", _do_link)
                ar.add_suffix(link)
                match_box.append(ar)

        tv.set_content(body); dlg.set_content(tv); dlg.present()

    def _create_link(self, a_id: str, b_id: str, kind: str) -> None:
        """Insert a FindingLink with canonical (min, max) ordering."""
        x, y = sorted((a_id, b_id))
        try:
            with get_session() as s:
                # Skip if already linked with this kind.
                exists = s.query(FindingLink).filter_by(
                    a_id=x, b_id=y, kind=kind).first()
                if exists is None:
                    s.add(FindingLink(a_id=x, b_id=y, kind=kind))
            # If this is a duplicate link, mark the *newer* one as duplicate.
            if kind == "duplicate":
                with get_session() as s:
                    a = s.get(Finding, a_id); b = s.get(Finding, b_id)
                    if a is not None and b is not None:
                        newer = a if (a.created_at or 0) > (b.created_at or 0) else b
                        newer.status = "duplicate"
            toaster = getattr(self._parent, "_toast_overlay", None)
            if toaster is not None:
                toaster.add_toast(Adw.Toast(title=f"Linked as {kind}"))
        except Exception as e:
            toaster = getattr(self._parent, "_toast_overlay", None)
            if toaster is not None:
                toaster.add_toast(Adw.Toast(title=f"Link failed: {e}"))
        self.refresh()

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
