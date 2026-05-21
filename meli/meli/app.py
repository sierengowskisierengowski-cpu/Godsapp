"""
Meli GTK4 Application entry point.
Initialises the database, starts the GTK app, and shows either
the setup wizard (first launch) or the lock screen.
"""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib, Gio, Gdk  # noqa: E402

import structlog
from meli.config import get_config
from meli.database import init_db
from meli.auth import is_setup_complete

log = structlog.get_logger()

APP_ID = "io.github.sierengowski.meli"


class MeliApplication(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.connect("activate", self._on_activate)
        self._main_window = None

    def _on_activate(self, app: Adw.Application) -> None:
        from meli.ui.main_window import MeliMainWindow
        from meli.config import get_config

        if self._main_window is None:
            self._main_window = MeliMainWindow(application=app)

            # Present the main window first so the compositor has a
            # parent surface to anchor the modal splash to. Without
            # this the splash can appear unparented on Wayland and
            # lose focus / z-order to other windows.
            self._main_window.present()

            cfg = get_config()
            splash_enabled = cfg.get("splash", "enabled", default=True)

            if splash_enabled:
                from meli.ui.splash_screen import SplashScreen
                splash = SplashScreen(
                    application=app,
                    transient_for=self._main_window,
                )
                splash.connect("splash-finished", lambda *_: self._after_splash())
                splash.present()
            else:
                self._post_splash_flow()
        else:
            self._main_window.present()

    def _after_splash(self) -> None:
        """Called once the splash animation completes."""
        if self._main_window is None:
            return
        # Main window was already presented before the splash; just run
        # the wizard/lock-screen flow now that the user can see it.
        self._post_splash_flow()

    def _post_splash_flow(self) -> None:
        """Show setup wizard on first launch, otherwise the lock screen."""
        if self._main_window is None:
            return
        if not is_setup_complete():
            log.info("First launch — showing setup wizard")
            GLib.idle_add(self._show_setup_wizard)
        else:
            log.info("Setup complete — showing lock screen")
            GLib.idle_add(self._main_window.show_lock_screen)

    def _show_setup_wizard(self) -> bool:
        from meli.ui.setup_wizard import SetupWizard
        wizard = SetupWizard(transient_for=self._main_window)
        wizard.connect("wizard-complete", self._on_wizard_complete)
        wizard.present()
        return False

    def _on_wizard_complete(self, wizard) -> None:
        log.info("Setup wizard complete")
        self._main_window.show_lock_screen()

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        self._init_app()
        self._setup_actions()
        self._load_css()

    def _init_app(self) -> None:
        try:
            init_db()
            log.info("Database initialised")
        except Exception as e:
            log.error("Database init failed", error=str(e))

    def _setup_actions(self) -> None:
        # Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Control>q"])

    def _load_css(self) -> None:
        """Load the Honey Trap theme from resources/css/style.css.

        Falls back to a minimal inline stylesheet if the file is missing
        (e.g. running from an old install that pre-dates the resource).
        """
        from pathlib import Path

        css = Gtk.CssProvider()
        css_path = Path(__file__).parent / "resources" / "css" / "style.css"
        try:
            if css_path.is_file():
                css.load_from_path(str(css_path))
                log.info("Loaded Honey Trap theme", path=str(css_path))
            else:
                raise FileNotFoundError(css_path)
        except Exception as e:
            log.warning("Falling back to inline CSS", error=str(e))
            css.load_from_string("""
                .meli-sidebar { background-color: alpha(@card_bg_color, 0.95); }
                .meli-header  { background-color: alpha(@headerbar_bg_color, 0.97); }
                .severity-critical { color: #dc2626; font-weight: bold; }
                .severity-high     { color: #ea7f1c; }
                .severity-medium   { color: #d4a017; }
                .severity-low      { color: #fde68a; }
                .severity-info     { color: #c2b8a3; }
                .amber-accent { color: #f59e0b; }
                .honey-accent { color: #d4a017; }
                .monospace { font-family: "JetBrains Mono", monospace; }
                .stat-card { border-radius: 14px; padding: 18px; }
            """)

        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display,
                css,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
        else:
            log.warning("No default display available for CSS provider")
