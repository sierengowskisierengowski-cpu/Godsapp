"""LightningOverlay — transparent click-through Cairo layer that strikes
random lightning across the main window with a faint distant-thunder
rumble synced to each visual bolt.

v0.4.1 polish pass:
- Frame-accurate audio sync (sound fires the same monotonic tick the bolt is born).
- Close (~20%) vs distant (~80%) strike depth with matching volume & visual scale.
- Sharper electrical core with brief afterglow & subtle scene-illumination flash.
- All knobs exposed in Settings → General → Storm.

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
from godsapp.core.logging import get_logger
from godsapp.core.settings import load_settings

log = get_logger(__name__)


# Audio pools — short sharp samples for close strikes, longer rolling
# samples for distant ambient rumble. Picked at random so it never repeats.
_CLOSE_STRIKE_WAVS = ("thunder_strike.wav", "thunder_crackle.wav", "thunder_close.wav")
_DISTANT_RUMBLE_WAVS = ("thunder_distant.wav", "thunder_rumble.wav", "thunder_rolling.wav")


# ── frequency presets (delay range in seconds between strikes) ──────────
_FREQ_PRESETS = {
    "sparse":    (60.0, 110.0),
    "moderate":  (15.0,  40.0),
    "frequent":  (6.0,   18.0),
}

# Preset multipliers for the strike/rumble volumes (applied on top of the
# user's 0–100 slider value so the preset still respects relative balance).
_PRESET_MULT = {
    "whisper":  0.15,
    "drizzle":  0.50,
    "standard": 1.00,
    "heavy":    1.60,
}


# ── bolt geometry ───────────────────────────────────────────────────────
def _jagged(x0, y0, x1, y1, jitter, depth, rng):
    if depth <= 0:
        return [(x0, y0), (x1, y1)]
    mx, my = (x0+x1)/2, (y0+y1)/2
    dx, dy = x1-x0, y1-y0
    nx, ny = -dy, dx
    L = math.hypot(nx, ny) or 1.0
    off = rng.uniform(-jitter, jitter)
    mx += nx/L * off; my += ny/L * off
    left  = _jagged(x0, y0, mx, my, jitter*0.55, depth-1, rng)
    right = _jagged(mx, my, x1, y1, jitter*0.55, depth-1, rng)
    return left[:-1] + right


def _build_bolt(w, h, rng, *, close: bool):
    """Close strikes are full-window; distant strikes are short + horizon-bound."""
    if close:
        sx = rng.uniform(w*0.10, w*0.90)
        ex = sx + rng.uniform(-w*0.18, w*0.18)
        main = _jagged(sx, -10, ex, h+10, jitter=min(w,h)*0.10, depth=8, rng=rng)
    else:
        # Distant: lives in the upper third, much shorter, sharper jitter
        sx = rng.uniform(w*0.10, w*0.90)
        ex = sx + rng.uniform(-w*0.08, w*0.08)
        y_top = rng.uniform(-10, h*0.05)
        y_bot = rng.uniform(h*0.18, h*0.34)
        main = _jagged(sx, y_top, ex, y_bot, jitter=min(w,h)*0.06, depth=6, rng=rng)
    branches = []
    n_b = (rng.randint(2, 4) if close else rng.randint(0, 2))
    for _ in range(n_b):
        i = rng.randint(len(main)//4, 3*len(main)//4)
        bx, by = main[i]
        scale = 1.0 if close else 0.55
        dx = rng.uniform(-w*0.16*scale, w*0.16*scale)
        dy = rng.uniform(h*0.08*scale, h*0.22*scale)
        branches.append(
            _jagged(bx, by, bx+dx, by+dy,
                    jitter=min(w,h)*0.05*scale, depth=5 if close else 4, rng=rng)
        )
    return main, branches


class _Strike:
    __slots__ = ("born", "duration", "main", "branches", "intensity", "close",
                 "afterglow_until")
    def __init__(self, born, duration, main, branches, intensity, close, afterglow_until):
        self.born = born; self.duration = duration
        self.main = main; self.branches = branches
        self.intensity = intensity; self.close = close
        self.afterglow_until = afterglow_until


class LightningOverlay(Gtk.DrawingArea):
    """Transparent click-through overlay painting random lightning strikes."""

    def __init__(self) -> None:
        super().__init__()
        self.set_hexpand(True); self.set_vexpand(True)
        self.set_can_target(False)
        self.set_can_focus(False)
        self.set_draw_func(self._draw, None)

        self._rng = random.Random()
        self._strikes: list[_Strike] = []
        self._flashes: list[tuple[float, float, float, bool]] = []  # (born,dur,inten,close)
        self._frame_tick_id = 0
        self._next_strike_id = 0
        self._settings_tick_id = 0
        self._destroyed = False
        # Count of currently-running scans rather than a boolean — multiple
        # concurrent scans must all complete before the storm resumes.
        self._active_scans = 0
        self._reload_settings()

        # First strike: 3–8s after launch
        delay_ms = int(self._rng.uniform(3.0, 8.0) * 1000)
        self._next_strike_id = GLib.timeout_add(delay_ms, self._on_strike_due)

        # Settings poll (10s) so toggling in Settings takes effect live.
        self._settings_tick_id = GLib.timeout_add_seconds(10, self._reload_settings)

        self.connect("unrealize", lambda *_: self._teardown())
        self.connect("destroy", lambda *_: self._teardown())

    # ── teardown ────────────────────────────────────────────────────────
    def _teardown(self) -> None:
        if self._destroyed:
            return
        self._destroyed = True
        for attr in ("_frame_tick_id", "_next_strike_id", "_settings_tick_id"):
            sid = getattr(self, attr, 0)
            if sid:
                try: GLib.source_remove(sid)
                except Exception: pass
                setattr(self, attr, 0)

    # ── settings ────────────────────────────────────────────────────────
    def _reload_settings(self) -> bool:
        if self._destroyed:
            return False
        try:
            ui = load_settings().ui
            self._enabled = bool(getattr(ui, "background_storm", True))
            self._vary_distance = bool(getattr(ui, "storm_distance_variation", True))
            self._pause_on_scans = bool(getattr(ui, "storm_pause_during_scans", True))
            preset = getattr(ui, "storm_preset", "standard")
            self._preset_mult = _PRESET_MULT.get(preset, 1.0)
            self._strike_vol = max(0, min(100, int(getattr(ui, "storm_strike_volume", 35))))
            self._rumble_vol = max(0, min(100, int(getattr(ui, "storm_rumble_volume", 18))))
            freq = getattr(ui, "storm_frequency", "moderate")
            self._min_delay, self._max_delay = _FREQ_PRESETS.get(freq, _FREQ_PRESETS["moderate"])
        except Exception:
            self._enabled = True
            self._vary_distance = True
            self._pause_on_scans = True
            self._preset_mult = 1.0
            self._strike_vol = 35
            self._rumble_vol = 18
            self._min_delay, self._max_delay = _FREQ_PRESETS["moderate"]
        return True

    # ── scan-pause hooks (called from MainWindow scan-event subscriber) ─
    def pause_for_scan(self) -> None:
        """Increment the active-scan counter. Must be paired with
        resume_after_scan() so concurrent scans don't prematurely resume."""
        self._active_scans += 1

    def resume_after_scan(self) -> None:
        if self._active_scans > 0:
            self._active_scans -= 1

    @property
    def _active(self) -> bool:
        return self._enabled and not (
            self._pause_on_scans and self._active_scans > 0
        )

    # ── strike scheduling ───────────────────────────────────────────────
    def _on_strike_due(self) -> bool:
        self._next_strike_id = 0
        if self._destroyed:
            return False
        if self._active:
            self._spawn_strike(time.monotonic())
        delay_ms = int(self._rng.uniform(self._min_delay, self._max_delay) * 1000)
        self._next_strike_id = GLib.timeout_add(delay_ms, self._on_strike_due)
        return False

    def _frame_tick(self) -> bool:
        if self._destroyed:
            self._frame_tick_id = 0
            return False
        now = time.monotonic()
        self._strikes = [s for s in self._strikes
                         if (now - s.born < s.duration) or now < s.afterglow_until]
        self._flashes = [f for f in self._flashes if now - f[0] < f[1]]
        if not (self._strikes or self._flashes):
            self._frame_tick_id = 0
            self.queue_draw()
            return False
        self.queue_draw()
        return True

    def _ensure_frame_tick(self) -> None:
        if self._frame_tick_id == 0 and not self._destroyed:
            self._frame_tick_id = GLib.timeout_add(33, self._frame_tick)

    def _spawn_strike(self, now: float) -> None:
        alloc = self.get_allocation()
        w, h = max(800, alloc.width), max(600, alloc.height)
        # Close vs distant pick (80/20 favoring distant when variation is on)
        if self._vary_distance:
            close = self._rng.random() < 0.20
        else:
            close = self._rng.random() < 0.50
        # 1 bolt for distant, 1–2 for close
        count = self._rng.randint(1, 2) if close else 1
        for k in range(count):
            main, branches = _build_bolt(w, h, self._rng, close=close)
            duration = self._rng.uniform(0.45, 0.75) if close else self._rng.uniform(0.20, 0.35)
            intensity = (self._rng.uniform(0.80, 1.0) if close
                         else self._rng.uniform(0.30, 0.55))
            # Afterglow: brief retinal-burn impression after the bolt dies
            afterglow = (0.45 if close else 0.18) * self._rng.uniform(0.8, 1.2)
            self._strikes.append(_Strike(
                born=now + k*0.04, duration=duration,
                main=main, branches=branches,
                intensity=intensity, close=close,
                afterglow_until=now + duration + afterglow,
            ))
        # Scene-illumination flash — close strikes get a brief but assertive
        # ~10% luminance lift; distant strikes get a very soft horizon glow.
        flash_inten = self._rng.uniform(0.40, 0.65) if close else self._rng.uniform(0.08, 0.18)
        flash_dur = 0.32 if close else 0.55
        self._flashes.append((now, flash_dur, flash_inten, close))

        # FRAME-ACCURATE AUDIO SYNC — fire the sound on the same tick the
        # bolt is born so the visual flash and the crack land together.
        self._play_thunder(close=close)

        self._ensure_frame_tick()

    def _play_thunder(self, *, close: bool) -> None:
        try:
            if close:
                vol = (self._strike_vol / 100.0) * self._preset_mult
                pool = _CLOSE_STRIKE_WAVS
            else:
                vol = (self._rumble_vol / 100.0) * self._preset_mult
                pool = _DISTANT_RUMBLE_WAVS
            # Slight per-strike randomness so it never feels mechanical
            vol *= self._rng.uniform(0.85, 1.05)
            vol = max(0.0, min(1.0, vol))
            if vol <= 0.005:
                return
            play_async(self._rng.choice(pool), volume=vol)
        except Exception:
            log.exception("storm thunder playback failed")

    # ── public ──────────────────────────────────────────────────────────
    def force_strike(self) -> None:
        if not self._active:
            return
        self._spawn_strike(time.monotonic())

    def intense_burst(self, count: int = 6, with_boom: bool = True) -> None:
        """Rapid-fire storm — used as the terminal-open WOW effect.
        Always close strikes; ignores the background_storm toggle since this
        is a direct response to a user action."""
        alloc = self.get_allocation()
        w, h = max(800, alloc.width), max(600, alloc.height)
        now = time.monotonic()
        for k in range(count):
            main, branches = _build_bolt(w, h, self._rng, close=True)
            duration = self._rng.uniform(0.40, 0.70)
            afterglow = 0.45 * self._rng.uniform(0.8, 1.2)
            self._strikes.append(_Strike(
                born=now + k*0.07, duration=duration,
                main=main, branches=branches,
                intensity=self._rng.uniform(0.85, 1.0), close=True,
                afterglow_until=now + duration + afterglow,
            ))
            self._flashes.append((now + k*0.07, 0.30,
                                  self._rng.uniform(0.55, 0.85), True))
        self._flashes.append((now + count*0.07, 0.55, 0.95, True))
        try:
            vol = max(0.05, (self._strike_vol/100.0) * self._preset_mult)
            play_async("thunder.wav" if with_boom else "thunder_distant.wav",
                       volume=min(1.0, vol*1.3))
        except Exception:
            pass
        self._ensure_frame_tick()

    # ── drawing ─────────────────────────────────────────────────────────
    def _draw(self, _area, cr, width, height, _user):
        if not (self._strikes or self._flashes):
            return
        now = time.monotonic()

        # Flash veils — close strikes get a warm white veil, distant gets
        # a cool blue horizon glow at the top of the window.
        for born, dur, inten, close in self._flashes:
            life = (now - born) / dur
            if not (0 <= life <= 1):
                continue
            decay = (1 - life) ** 1.6
            a = decay * 0.30 * inten
            if close:
                cr.set_source_rgba(1.0, 0.98, 0.92, a)
                cr.rectangle(0, 0, width, height); cr.fill()
            else:
                # Top-down soft sky glow
                grad = cairo.LinearGradient(0, 0, 0, height*0.5)
                grad.add_color_stop_rgba(0.0, 0.85, 0.92, 1.0, a*0.9)
                grad.add_color_stop_rgba(1.0, 0.85, 0.92, 1.0, 0.0)
                cr.set_source(grad)
                cr.rectangle(0, 0, width, height*0.5); cr.fill()

        # Bolts + afterglow
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        for s in self._strikes:
            age = now - s.born
            if age < 0:
                continue
            life = age / s.duration
            if life <= 1:
                # 3-stage curve: snap on / hold bright / decay
                if life < 0.04:
                    a = life / 0.04
                elif life < 0.28:
                    a = 1.0
                else:
                    a = max(0.0, 1.0 - (life - 0.28) / 0.72)
                a *= s.intensity
                self._draw_bolt(cr, s.main, a,
                                1.0 if s.close else 0.55, close=s.close)
                for br in s.branches:
                    self._draw_bolt(cr, br, a*0.7,
                                    0.55 if s.close else 0.30, close=s.close)
            elif now < s.afterglow_until:
                # Faint retinal-burn afterglow — a much dimmer ghost of the bolt
                remaining = (s.afterglow_until - now) / max(0.01, s.afterglow_until - (s.born + s.duration))
                a = (remaining ** 2) * 0.18 * s.intensity
                self._draw_bolt(cr, s.main, a,
                                0.70 if s.close else 0.40, close=s.close)

    def _draw_bolt(self, cr, pts, alpha: float, width_scale: float, *, close: bool):
        if alpha <= 0 or len(pts) < 2:
            return
        # Distant bolts: paler & narrower; close bolts: full sharp core
        if close:
            layers = [
                (24*width_scale, (0.75, 0.85, 1.0, 0.10*alpha)),
                (13*width_scale, (0.85, 0.92, 1.0, 0.24*alpha)),
                (6*width_scale,  (0.99, 0.88, 0.50, 0.60*alpha)),
                (2.2*width_scale,(1.0,  1.0,  1.0,  0.98*alpha)),
                (0.9*width_scale,(1.0,  1.0,  0.95, 1.00*alpha)),  # razor core
            ]
        else:
            layers = [
                (10*width_scale, (0.70, 0.82, 1.0, 0.08*alpha)),
                (5*width_scale,  (0.85, 0.92, 1.0, 0.22*alpha)),
                (1.8*width_scale,(0.96, 0.99, 1.0, 0.85*alpha)),
            ]
        for w_px, rgba in layers:
            cr.set_source_rgba(*rgba)
            cr.set_line_width(w_px)
            cr.move_to(*pts[0])
            for x, y in pts[1:]:
                cr.line_to(x, y)
            cr.stroke()
