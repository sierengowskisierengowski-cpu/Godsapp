"""Settings view: theme, API server, database URL."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from godsapp import __version__
from godsapp.core import paths
from godsapp.core.settings import load_settings, save_settings


class SettingsView(Gtk.Box):
    def __init__(self, parent) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(20); self.set_margin_bottom(20)
        self.set_margin_start(20); self.set_margin_end(20)
        self._parent = parent
        self._settings = load_settings()

        title = Gtk.Label(label="Settings", xalign=0)
        title.add_css_class("view-title")
        self.append(title)

        # API group
        api_group = Adw.PreferencesGroup(title="REST API",
                                         description="Optional local API (binds 127.0.0.1).")
        self._api_enabled = Adw.SwitchRow(title="Enable API server")
        self._api_enabled.set_active(self._settings.api.enabled)
        self._api_port = Adw.SpinRow.new_with_range(1, 65535, 1)
        self._api_port.set_title("Port")
        self._api_port.set_value(self._settings.api.port)
        self._api_token = Adw.SwitchRow(title="Require token (~/.config/godsapp/api.token)")
        self._api_token.set_active(self._settings.api.require_token)
        api_group.add(self._api_enabled)
        api_group.add(self._api_port)
        api_group.add(self._api_token)
        self.append(api_group)

        # DB group
        db_group = Adw.PreferencesGroup(
            title="Database",
            description="Leave empty for SQLite. Set to a PostgreSQL URL for power use.",
        )
        self._db_url = Adw.EntryRow()
        self._db_url.set_title("Database URL")
        self._db_url.set_text(self._settings.database.url or "")
        db_group.add(self._db_url)
        self.append(db_group)

        # UI group
        ui_group = Adw.PreferencesGroup(title="Interface")
        self._matrix_switch = Adw.SwitchRow(title="Matrix-style text scramble on hover")
        self._matrix_switch.set_active(self._settings.ui.matrix_scramble)
        ui_group.add(self._matrix_switch)
        self.append(ui_group)

        # Save
        save_btn = Gtk.Button(label="Save settings")
        save_btn.add_css_class("suggested-action")
        save_btn.set_halign(Gtk.Align.START)
        save_btn.connect("clicked", lambda *_: self._save())
        self.append(save_btn)

        # Footer
        footer = Gtk.Label(
            label=f"GodsApp {__version__}  ·  config {paths.CONFIG_DIR}  ·  data {paths.DATA_DIR}",
            xalign=0,
        )
        footer.add_css_class("dim-label")
        footer.set_wrap(True)
        self.append(footer)

    def _save(self) -> None:
        self._settings.api.enabled = self._api_enabled.get_active()
        self._settings.api.port = int(self._api_port.get_value())
        self._settings.api.require_token = self._api_token.get_active()
        self._settings.database.url = self._db_url.get_text().strip() or None
        self._settings.ui.matrix_scramble = self._matrix_switch.get_active()
        save_settings(self._settings)
