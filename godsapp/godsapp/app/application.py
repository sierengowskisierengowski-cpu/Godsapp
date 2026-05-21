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
from godsapp.core.scheduler import scheduler
from godsapp.core.settings import load_settings
from godsapp.db import init_db
from godsapp.tools import registry
from godsapp.ui.login import show_login
from godsapp.ui.main_window import MainWindow
from godsapp.ui.views.splash import show_splash

log = get_logger(__name__)


class GodsAppApplication(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=__app_id__,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.set_resource_base_path(None)
        self._window: MainWindow | None = None
        self._splash = None

    def do_startup(self) -> None:  # type: ignore[override]
        Adw.Application.do_startup(self)

        paths.ensure_directories()
        setup_logging()
        init_db()
        registry.load_builtin()
        if load_settings().plugins.auto_load:
            registry.load_plugins()

        self._install_css()
        self._install_actions()

        # Start scheduler in the background if enabled.
        try:
            if load_settings().scheduler.enabled:
                scheduler.start()
        except Exception:
            log.exception("scheduler failed to start")

    def do_activate(self) -> None:  # type: ignore[override]
        if self._window is not None:
            self._window.present()
            return
        try:
            wants_splash = load_settings().ui.show_splash
        except Exception:
            wants_splash = True

        def _show_main() -> None:
            if self._window is None:
                self._window = MainWindow(self)
            self._window.present()
            # First-launch onboarding tour. No-op if already completed.
            try:
                GLib.idle_add(lambda: (self._window.show_onboarding(), False)[1])
            except Exception:
                log.exception("onboarding launch failed")

        def _show_login_then_main() -> None:
            show_login(self, on_success=_show_main)

        if wants_splash:
            self._splash = show_splash(self, on_done=_show_login_then_main)
        else:
            _show_login_then_main()

    def do_shutdown(self) -> None:  # type: ignore[override]
        try:
            scheduler.stop()
        except Exception:
            pass
        Adw.Application.do_shutdown(self)

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
        add("palette", lambda: self._window.open_command_palette() if self._window else None)
        add("refresh", lambda: self._window.refresh_current() if self._window else None)
        self.set_accels_for_action("app.quit", ["<Primary>q"])
        self.set_accels_for_action("app.palette", ["<Primary>k"])
        self.set_accels_for_action("app.refresh", ["F5"])

    def _show_about(self) -> None:
        about = Adw.AboutWindow(
            transient_for=self._window,
            application_name=__app_name__,
            application_icon=__app_id__,
            version=__version__,
            developer_name="Joseph Sierengowski",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/sierengowskisierengowski-cpu/Godsapp",
            issue_url="https://github.com/sierengowskisierengowski-cpu/Godsapp/issues",
            copyright="© 2026 Joseph Sierengowski",
            comments="Professional security auditing and research suite.",
        )
        about.present()


def main(argv: list[str] | None = None) -> int:
    app = GodsAppApplication()
    return app.run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
