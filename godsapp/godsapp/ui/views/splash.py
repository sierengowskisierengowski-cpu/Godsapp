"""Splash window — pulsating logo while the main window initialises."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from godsapp import __app_name__, __version__


class SplashWindow(Adw.Window):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app)
        self.set_default_size(360, 360)
        self.set_decorated(False)
        self.set_resizable(False)
        self.add_css_class("godsapp-splash")
        self.add_css_class("godsapp-window")
        self.add_css_class("state-idle")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14,
                      halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        box.set_margin_top(40); box.set_margin_bottom(40)
        box.set_margin_start(40); box.set_margin_end(40)

        try:
            from importlib.resources import files
            svg_path = files("godsapp.resources.icons").joinpath("godsapp-logo.svg")
            img = Gtk.Image.new_from_file(str(svg_path))
            img.set_pixel_size(140)
            img.add_css_class("bolt-logo")
            img.add_css_class("splash-logo")
            box.append(img)
        except Exception:
            lbl = Gtk.Label(label="☁⚡"); lbl.add_css_class("bolt-logo")
            lbl.add_css_class("splash-logo"); box.append(lbl)

        title = Gtk.Label(label=__app_name__.upper())
        title.add_css_class("splash-title")
        box.append(title)
        ver = Gtk.Label(label=f"v{__version__} · Joseph Sierengowski")
        ver.add_css_class("splash-version"); ver.add_css_class("dim-label")
        box.append(ver)

        self._progress = Gtk.Label(label="initialising…")
        self._progress.add_css_class("splash-progress")
        self._progress.add_css_class("dim-label")
        box.append(self._progress)

        self.set_content(box)

    def set_progress(self, text: str) -> None:
        self._progress.set_text(text)


def show_splash(app: Adw.Application, *, duration_ms: int = 1400,
                on_done: callable = lambda: None) -> SplashWindow:
    splash = SplashWindow(app)
    splash.present()
    def _close() -> bool:
        try:
            splash.close()
        except Exception:
            pass
        try:
            on_done()
        except Exception:
            pass
        return False
    GLib.timeout_add(duration_ms, _close)
    return splash
