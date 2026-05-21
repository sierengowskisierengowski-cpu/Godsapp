"""LightningOverlay — transparent click-through Cairo layer that strikes
random lightning across the main window every 15-40 seconds, paired with
a faint distant-thunder rumble.

The window's baked sky + clouds CSS stays untouched; this widget only
paints jagged bolts and brief white flash veils ON TOP of everything.

Author: Joseph Sierengowski.
"""
from __future__ import annotations

import math
import random
import time

import cairo
import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk  # noqa: E402

from godsapp.core.audio import play_async

# Pool of ambient/strike thunder sounds. Picked at random for every strike so
# the soundscape never repeats. Bundled .wav files live in resources/audio/.
_AMBIENT_THUNDER = (
    "thunder_distant.wav", "thunder_rumble.wav", "thunder_rolling.wav",
    "thunder_distant.wav", "thunder_rumble.wav",
)
_STRIKE_THUNDER = (
    "thunder_strike.wav", "thunder_crackle.wav", "thunder_close.wav",
    "thunder_strike.wav",
)
from godsapp.core.logging import get_logger
from godsapp.core.settings import load_settings

log = get_logger(__name__)


# ── shared bolt geometry (mirrored from splash.py to keep splash standalone)
def _jagged(x0: float, y0: float, x1: float, y1: float, jitter: float,
            depth: int, rng: random.Random) -> list[tuple[float, float]]:
    if depth <= 0:
        return [(x0, y0), (x1, y1)]
    mx, my = (x0+x1)/2, (y0+y1)/2
    dx, dy = x1-x0, y1-y0
    nx, ny = -dy, dx
    L = math.hypot(nx, ny) or 1.0
    off = rng.uniform(-jitter, jitter)
    mx += nx/L * off; my += ny/L * off
    left = _jagged(x0, y0, mx, my, jitter*0.55, depth-1, rng)
    right = _jagged(mx, my, x1, y1, jitter*0.55, depth-1, rng)
    return left[:-1] + right


def _build_bolt(w: float, h: float, rng: random.Random):
    sx = rng.uniform(w*0.10, w*0.90)
    ex = sx + rng.uniform(-w*0.20, w*0.20)
    main = _jagged(sx, -10, ex, h+10, jitter=min(w,h)*0.09, depth=7, rng=rng)
    branches = []
    for _ in range(rng.randint(1, 3)):
        i = rng.randint(len(main)//4, 3*len(main)//4)
        bx, by = main[i]
        dx = rng.uniform(-w*0.15, w*0.15)
        dy = rng.uniform(h*0.08, h*0.22)
        branches.append(
            _jagged(bx, by, bx+dx, by+dy, jitter=min(w,h)*0.04, depth=5, rng=rng)
        )
    return main, branches


class _Strike:
    __slots__ = ("born", "duration", "main", "branches", "intensity")
    def __init__(self, born, duration, main, branches, intensity):
        self.born = born; self.duration = duration
        self.main = main; self.branches = branches; self.intensity = intensity


class LightningOverlay(Gtk.DrawingArea):
    """Transparent click-through overlay painting random lightning strikes."""

    # strike cadence (seconds) — randomized inside this range
    MIN_DELAY = 15.0
    MAX_DELAY = 40.0

    def __init__(self) -> None:
        super().__init__()
        self.set_hexpand(True); self.set_vexpand(True)
        self.set_can_target(False)              # click-through
        self.set_can_focus(False)
        self.set_draw_func(self._draw, None)

        self._rng = random.Random()
        self._strikes: list[_Strike] = []
        self._flashes: list[tuple[float, float, float]] = []
        self._frame_tick_id = 0       # 30fps active-render source
        self._next_strike_id = 0      # one-shot "fire next strike" source
        self._settings_tick_id = 0    # low-frequency settings poll
        self._enabled = True
        self._destroyed = False
        self._reload_settings()

        # Schedule first strike (one-shot, no constant wake).
        delay_ms = int(self._rng.uniform(3.0, 8.0) * 1000)
        self._next_strike_id = GLib.timeout_add(delay_ms, self._on_strike_due)

        # Poll settings infrequently so toggling background_storm takes effect
        # without restarting (event-driven would be ideal but settings.save
        # currently has no signal bus — 10s poll is a deliberate tradeoff).
        self._settings_tick_id = GLib.timeout_add_seconds(10, self._reload_settings)

        # Clean up all GLib sources when the widget goes away.
        self.connect("unrealize", lambda *_: self._teardown())
        self.connect("destroy", lambda *_: self._teardown())

    # ── teardown ─────────────────────────────────────────────────────────
    def _teardown(self) -> None:
        if self._destroyed:
            return
        self._destroyed = True
        for attr in ("_frame_tick_id", "_next_strike_id", "_settings_tick_id"):
            sid = getattr(self, attr, 0)
            if sid:
                try:
                    GLib.source_remove(sid)
                except Exception:
                    pass
                setattr(self, attr, 0)

    # ── settings ─────────────────────────────────────────────────────────
    def _reload_settings(self) -> bool:
        if self._destroyed:
            return False
        try:
            ui = load_settings().ui
            self._enabled = bool(getattr(ui, "background_storm", True))
        except Exception:
            self._enabled = True
        return True

    # ── strike scheduling (one-shot, no constant wake) ──────────────────
    def _on_strike_due(self) -> bool:
        self._next_strike_id = 0
        if self._destroyed:
            return False
        if self._enabled:
            self._spawn_strike(time.monotonic())
        # Schedule the next one no matter what (cheap; one wake per ~15-40s)
        delay_ms = int(self._rng.uniform(self.MIN_DELAY, self.MAX_DELAY) * 1000)
        self._next_strike_id = GLib.timeout_add(delay_ms, self._on_strike_due)
        return False  # one-shot

    # ── animation loop (only runs while strikes/flashes are active) ─────
    def _frame_tick(self) -> bool:
        if self._destroyed:
            self._frame_tick_id = 0
            return False
        now = time.monotonic()
        self._strikes = [s for s in self._strikes if now - s.born < s.duration]
        self._flashes = [f for f in self._flashes if now - f[0] < f[1]]
        if not (self._strikes or self._flashes):
            self._frame_tick_id = 0
            self.queue_draw()  # final clear
            return False
        self.queue_draw()
        return True

    def _ensure_frame_tick(self) -> None:
        if self._frame_tick_id == 0 and not self._destroyed:
            self._frame_tick_id = GLib.timeout_add(33, self._frame_tick)

    def _spawn_strike(self, now: float) -> None:
        alloc = self.get_allocation()
        w, h = max(800, alloc.width), max(600, alloc.height)
        # 1-2 bolts per strike, slightly staggered
        count = self._rng.randint(1, 2)
        for k in range(count):
            main, branches = _build_bolt(w, h, self._rng)
            self._strikes.append(_Strike(
                born=now + k*0.06,
                duration=self._rng.uniform(0.45, 0.75),
                main=main, branches=branches,
                intensity=self._rng.uniform(0.55, 0.95),
            ))
        # subtle full-window flash (capped low so the UI stays readable)
        self._flashes.append((now, 0.35, self._rng.uniform(0.35, 0.55)))
        # distant thunder, only if user has sounds on
        try:
            # Pick a different variant every time so it never feels repeated.
            pool = _STRIKE_THUNDER if self._rng.random() < 0.35 else _AMBIENT_THUNDER
            play_async(self._rng.choice(pool))
        except Exception:
            log.exception("storm thunder playback failed")
        # Kick the 30fps render loop for the duration of this strike.
        self._ensure_frame_tick()

    # ── public: force a strike now (for testing or scan events) ─────────
    def force_strike(self) -> None:
        if not self._enabled:
            return
        self._spawn_strike(time.monotonic())

    def intense_burst(self, count: int = 6, with_boom: bool = True) -> None:
        """Rapid-fire storm — used as the terminal-open WOW effect.

        Ignores the user's `background_storm` toggle because this is a
        direct response to a user-initiated action (opening the terminal).
        """
        alloc = self.get_allocation()
        w, h = max(800, alloc.width), max(600, alloc.height)
        now = time.monotonic()
        for k in range(count):
            main, branches = _build_bolt(w, h, self._rng)
            self._strikes.append(_Strike(
                born=now + k*0.07,
                duration=self._rng.uniform(0.40, 0.70),
                main=main, branches=branches,
                intensity=self._rng.uniform(0.85, 1.0),
            ))
            # Each strike gets its own flash veil for the rapid-fire effect
            self._flashes.append((now + k*0.07, 0.30, self._rng.uniform(0.55, 0.85)))
        # Closing white wash
        self._flashes.append((now + count*0.07, 0.55, 0.95))
        try:
            play_async("thunder.wav" if with_boom else "thunder_distant.wav")
        except Exception:
            pass
        self._ensure_frame_tick()

    # ── drawing ──────────────────────────────────────────────────────────
    def _draw(self, _area, cr, width, height, _user):
        if not (self._strikes or self._flashes):
            return  # fully transparent when idle
        now = time.monotonic()

        # Flash veils first so bolts paint over them
        for born, dur, inten in self._flashes:
            life = (now - born) / dur
            if 0 <= life <= 1:
                a = (1 - life) ** 1.6 * 0.32 * inten
                cr.set_source_rgba(1.0, 0.98, 0.92, a)
                cr.rectangle(0, 0, width, height); cr.fill()

        # Bolts
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        for s in self._strikes:
            age = now - s.born
            if age < 0:
                continue
            life = age / s.duration
            if life > 1:
                continue
            if life < 0.05:
                a = life / 0.05
            elif life < 0.30:
                a = 1.0
            else:
                a = max(0.0, 1.0 - (life - 0.30) / 0.70)
            a *= s.intensity
            self._draw_bolt(cr, s.main, a, 1.0)
            for br in s.branches:
                self._draw_bolt(cr, br, a*0.7, 0.55)

    def _draw_bolt(self, cr, pts, alpha: float, width_scale: float):
        if alpha <= 0 or len(pts) < 2:
            return
        for w_px, rgba in [
            (22*width_scale, (0.75, 0.85, 1.0, 0.10*alpha)),
            (12*width_scale, (0.85, 0.92, 1.0, 0.22*alpha)),
            (6*width_scale,  (0.96, 0.85, 0.45, 0.55*alpha)),
            (2.5*width_scale,(1.0,  1.0,  1.0,  0.95*alpha)),
        ]:
            cr.set_source_rgba(*rgba)
            cr.set_line_width(w_px)
            cr.move_to(*pts[0])
            for x, y in pts[1:]:
                cr.line_to(x, y)
            cr.stroke()
