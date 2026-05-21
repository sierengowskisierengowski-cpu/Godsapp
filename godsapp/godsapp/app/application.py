"""GTK4 + libadwaita Application entrypoint."""
from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from godsapp import __app_id__, __app_name__, __version__
from godsapp.core import paths
from godsapp.core.logging import get_logger, setup_logging
from godsapp.db import init_db
from godsapp.tools import registry
from godsapp.ui.main_window import MainWindow

log = get_logger(__name__)


class GodsAppApplication(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=__app_id__,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.set_resource_base_path(None)
        self._window: MainWindow | None = None

    def do_startup(self) -> None:  # type: ignore[override]
        Adw.Application.do_startup(self)

        paths.ensure_directories()
        setup_logging()
        init_db()
        registry.load_builtin()
        registry.load_plugins()

        self._install_css()
        self._install_actions()

    def do_activate(self) -> None:  # type: ignore[override]
        if self._window is None:
            self._window = MainWindow(self)
        self._window.present()

    def do_command_line(self, command_line) -> int:  # type: ignore[override]
        self.activate()
        return 0

    def _install_css(self) -> None:
        from importlib.resources import files
        provider = Gtk.CssProvider()
        try:
            css = files("godsapp.resources.css").joinpath("style.css").read_text()
            provider.load_from_data(css.encode("utf-8"))
        except Exception:
            log.exception("failed to load CSS")
            return
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def _install_actions(self) -> None:
        def add(name: str, callback) -> None:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda *_: callback())
            self.add_action(action)

        add("quit", self.quit)
        add("about", self._show_about)
        self.set_accels_for_action("app.quit", ["<Primary>q"])

    def _show_about(self) -> None:
        about = Adw.AboutWindow(
            transient_for=self._window,
            application_name=__app_name__,
            application_icon=__app_id__,
            version=__version__,
            developer_name="Joseph Sierengowski",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/jsierengowski/godsapp",
            issue_url="https://github.com/jsierengowski/godsapp/issues",
            copyright="© 2026 Joseph Sierengowski",
            comments="Professional security auditing and research suite.",
        )
        about.present()


def main(argv: list[str] | None = None) -> int:
    app = GodsAppApplication()
    return app.run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
