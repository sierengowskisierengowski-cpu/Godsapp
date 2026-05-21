"""Splash window — cinematic Mount Olympus lightning storm.

Real Cairo-drawn jagged lightning bolts (no emoji), full-window white
flash overlays timed to each strike, deep thunder audio playback, and a
fade-up logo + title that lands as the storm peaks.

Author: Joseph Sierengowski.
"""
from __future__ import annotations

import math
import random
import time

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from godsapp import __app_name__, __version__
from godsapp.core.audio import play_async
from godsapp.core.logging import get_logger

log = get_logger(__name__)


# ── lightning geometry ──────────────────────────────────────────────────
def _jagged(x0: float, y0: float, x1: float, y1: float, jitter: float,
            depth: int, rng: random.Random) -> list[tuple[float, float]]:
    """Recursive midpoint displacement → jagged polyline."""
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


def _build_bolt(w: float, h: float, rng: random.Random) -> tuple[list[tuple[float,float]], list[list[tuple[float,float]]]]:
    """Main jagged spine + a few side branches."""
    sx = rng.uniform(w*0.15, w*0.85)
    ex = sx + rng.uniform(-w*0.15, w*0.15)
    main = _jagged(sx, -10, ex, h+10, jitter=min(w,h)*0.10, depth=7, rng=rng)
    branches: list[list[tuple[float,float]]] = []
    for _ in range(rng.randint(2, 4)):
        i = rng.randint(len(main)//4, 3*len(main)//4)
        bx, by = main[i]
        dx = rng.uniform(-w*0.18, w*0.18)
        dy = rng.uniform(h*0.10, h*0.28)
        branch = _jagged(bx, by, bx+dx, by+dy, jitter=min(w,h)*0.05, depth=5, rng=rng)
        branches.append(branch)
    return main, branches


class _Strike:
    __slots__ = ("born", "duration", "main", "branches", "intensity")
    def __init__(self, born: float, duration: float, main, branches, intensity: float):
        self.born = born; self.duration = duration
        self.main = main; self.branches = branches; self.intensity = intensity


# ── window ──────────────────────────────────────────────────────────────
class SplashWindow(Adw.Window):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app)
        self.set_decorated(False)
        self.set_resizable(False)
        self.add_css_class("godsapp-splash")
        self.add_css_class("godsapp-window")
        self.add_css_class("state-idle")
        self.set_default_size(1280, 800)

        # Fullscreen for the WOW factor; falls back to a large window if
        # the compositor refuses (some kiosk setups).
        try:
            self.fullscreen()
        except Exception:
            pass

        # Drawing area covers the entire window; everything renders here
        # so we get a single composited paint per frame.
        self._da = Gtk.DrawingArea()
        self._da.set_hexpand(True); self._da.set_vexpand(True)
        self._da.set_draw_func(self._draw, None)

        # Click / Space / Enter / Esc to dismiss early.
        click = Gtk.GestureClick.new()
        click.connect("released", lambda *_: self._dismiss_early())
        self._da.add_controller(click)
        key = Gtk.EventControllerKey.new()
        key.connect("key-pressed", self._on_key)
        self.add_controller(key)

        self.set_content(self._da)

        # Storm state
        self._start = time.monotonic()
        self._strikes: list[_Strike] = []
        self._flashes: list[tuple[float, float, float]] = []  # (born, dur, intensity)
        self._rng = random.Random()
        self._on_done = None
        self._done_called = False
        self._dismissed = False

        # 60fps tick
        self._tick_id = GLib.timeout_add(16, self._tick)

        # Storm schedule (relative seconds) — must line up with thunder.wav cracks
        # cracks in audio: 0.55, 1.55, 2.55; boom 3.30
        self._schedule = [
            (0.55, 0.55, 0.85),   # strike 1
            (1.55, 0.60, 0.95),   # strike 2
            (2.55, 0.65, 1.05),   # strike 3
            (3.30, 0.90, 1.20),   # boom
            (4.40, 0.55, 0.95),   # encore strike
            (5.10, 0.85, 1.15),   # finale
        ]
        self._fired = [False]*len(self._schedule)

        # Real boot-step counts so the splash narrates what actually happened
        # during startup, not mystical filler. All cheap lookups — splash runs
        # AFTER do_startup() so init_db/load_builtin already completed.
        try:
            from godsapp.tools import registry as _reg
            n_tools = sum(len(v) for v in _reg.by_category().values())
            n_cats = len([v for v in _reg.by_category().values() if v])
        except Exception:
            n_tools, n_cats = 0, 0
        try:
            from godsapp.core.settings import load_settings as _ls
            n_plugins = len(_ls().plugins.enabled or []) if _ls().plugins.auto_load else 0
        except Exception:
            n_plugins = 0
        try:
            from sqlalchemy import select as _sel, func as _fn
            from godsapp.db import Finding as _F, Workspace as _W, get_session as _gs
            with _gs() as _s:
                n_ws = _s.execute(_sel(_fn.count()).select_from(_W)).scalar() or 0
                n_fnd = _s.execute(_sel(_fn.count()).select_from(_F)).scalar() or 0
        except Exception:
            n_ws, n_fnd = 0, 0

        # Strike-synchronised announcements: each strike fires a real-step label.
        # (when, headline, subline)  — when == schedule time of the matching strike.
        self._strike_labels: list[tuple[float, str, str]] = [
            (0.55, "FORGING THE FOUNDATION", "config + log + data paths armed"),
            (1.55, "AWAKENING THE ARCHIVE",  f"database online · {n_ws} workspace(s) · {n_fnd} finding(s)"),
            (2.55, "SUMMONING THE ARSENAL",  f"{n_tools} tools across {n_cats} categories registered"),
            (3.30, "BINDING THE PLUGINS",    f"plugin loader ready · {n_plugins} enabled"),
            (4.40, "TUNING THE SCHEDULER",   "background runner & audit trail online"),
            (5.10, "OPENING THE GATES",      "all systems hot — strike when ready"),
        ]
        # Most-recent (born_t, headline, subline) — what the painter renders.
        self._active_label: tuple[float, str, str] | None = None

    # ── input ───────────────────────────────────────────────────────────
    def _on_key(self, _ctrl, keyval, _kc, _state) -> bool:
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_space, Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._dismiss_early()
            return True
        return False

    def _dismiss_early(self) -> None:
        if self._dismissed:
            return
        self._dismissed = True
        self._finish()

    # ── tick / scheduling ───────────────────────────────────────────────
    def _tick(self) -> bool:
        if self._dismissed:
            return False
        now = time.monotonic()
        t = now - self._start
        # Fire scheduled strikes
        for i, (when, dur, inten) in enumerate(self._schedule):
            if not self._fired[i] and t >= when:
                self._fired[i] = True
                self._spawn_storm(dur, inten, finale=(i == len(self._schedule)-1))
                # Match this strike to its boot-step announcement (if any) so
                # the headline appears the instant the bolt cracks.
                for sw, head, sub in self._strike_labels:
                    if abs(sw - when) < 0.01:
                        self._active_label = (now, head, sub)
                        break
        # Cull expired strikes/flashes
        self._strikes = [s for s in self._strikes if now - s.born < s.duration]
        self._flashes = [f for f in self._flashes if now - f[0] < f[1]]
        self._da.queue_draw()
        # End at ~6.4s — gives the user time to soak in the storm before the gate opens.
        if t >= 6.4:
            self._finish()
            return False
        return True

    def _spawn_storm(self, dur: float, inten: float, finale: bool) -> None:
        alloc = self._da.get_allocation()
        w, h = max(800, alloc.width), max(600, alloc.height)
        now = time.monotonic()
        count = 5 if finale else self._rng.randint(1, 2)
        for k in range(count):
            main, branches = _build_bolt(w, h, self._rng)
            self._strikes.append(_Strike(
                born=now + k*0.04,
                duration=dur * self._rng.uniform(0.75, 1.0),
                main=main, branches=branches,
                intensity=inten * self._rng.uniform(0.7, 1.0),
            ))
        # full-window white flash
        self._flashes.append((now, 0.45 if not finale else 0.75, inten))

    def _current_announcement(self, now: float) -> tuple[str, str, float] | None:
        """Return (headline, subline, alpha 0..1) for the live strike label.
        Animation: quick snap-on (60ms) → hold (700ms) → fade-out (700ms)."""
        if self._active_label is None:
            return None
        born, head, sub = self._active_label
        age = now - born
        SNAP, HOLD, FADE = 0.06, 0.70, 0.70
        if age < 0:
            return None
        if age < SNAP:
            a = age / SNAP
        elif age < SNAP + HOLD:
            a = 1.0
        elif age < SNAP + HOLD + FADE:
            a = 1.0 - (age - SNAP - HOLD) / FADE
        else:
            return None
        return head, sub, max(0.0, min(1.0, a))

    # ── draw ────────────────────────────────────────────────────────────
    def _draw(self, _area, cr, width, height, _user):
        now = time.monotonic()
        t = now - self._start

        # Background gradient: deep twilight → black at horizon
        bg = cairo.LinearGradient(0, 0, 0, height)
        bg.add_color_stop_rgb(0.0, 0.04, 0.07, 0.14)
        bg.add_color_stop_rgb(0.55, 0.02, 0.04, 0.08)
        bg.add_color_stop_rgb(1.0, 0.00, 0.00, 0.00)
        cr.set_source(bg)
        cr.rectangle(0, 0, width, height); cr.fill()

        # Soft cloud layers — radial gradients, drifting
        for cy, radius, alpha, drift in [
            (height*0.20, max(width,height)*0.55, 0.18, 30),
            (height*0.55, max(width,height)*0.50, 0.10, -22),
            (height*0.85, max(width,height)*0.45, 0.14, 14),
        ]:
            cx = width*0.5 + math.sin(t*0.4 + drift) * 60
            rg = cairo.RadialGradient(cx, cy, 0, cx, cy, radius)
            rg.add_color_stop_rgba(0.0, 0.55, 0.65, 0.80, alpha)
            rg.add_color_stop_rgba(1.0, 0.0, 0.0, 0.0, 0.0)
            cr.set_source(rg)
            cr.rectangle(0, 0, width, height); cr.fill()

        # Lightning bolts
        for s in self._strikes:
            age = now - s.born
            if age < 0: continue
            life = age / s.duration
            if life > 1: continue
            # 3-stage curve: snap on, hold bright, decay
            if life < 0.05:
                a = life / 0.05
            elif life < 0.35:
                a = 1.0
            else:
                a = max(0.0, 1.0 - (life-0.35) / 0.65)
            a *= s.intensity
            self._draw_bolt(cr, s.main, a, core=True)
            for br in s.branches:
                self._draw_bolt(cr, br, a*0.7, core=True, width_scale=0.55)

        # Full-window white flash overlays
        for born, dur, inten in self._flashes:
            age = now - born
            life = age / dur
            if 0 <= life <= 1:
                a = (1 - life) ** 1.4 * 0.55 * inten
                cr.set_source_rgba(1, 1, 1, a)
                cr.rectangle(0, 0, width, height); cr.fill()

        # Centered logo + title — fade in over first second, then live
        self._draw_titles(cr, width, height, t)

    def _draw_bolt(self, cr, pts: list[tuple[float,float]], alpha: float,
                   core: bool = True, width_scale: float = 1.0):
        if alpha <= 0 or len(pts) < 2: return
        # Outer halo
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        for w_px, rgba in [
            (22*width_scale, (0.75, 0.85, 1.0, 0.10*alpha)),
            (12*width_scale, (0.85, 0.92, 1.0, 0.22*alpha)),
            (6*width_scale,  (0.96, 0.85, 0.45, 0.55*alpha)),  # gold mid
            (2.5*width_scale,(1.0,  1.0,  1.0,  0.95*alpha)),  # bright core
        ]:
            cr.set_source_rgba(*rgba)
            cr.set_line_width(w_px)
            cr.move_to(*pts[0])
            for x, y in pts[1:]:
                cr.line_to(x, y)
            cr.stroke()

    def _draw_titles(self, cr, width, height, t: float):
        # Logo (drawn cloud + bolt directly, scalable)
        cx, cy = width/2, height/2 - 60
        # Fade timeline
        fade_logo  = max(0.0, min(1.0, (t - 0.1) / 0.8))
        fade_title = max(0.0, min(1.0, (t - 0.6) / 0.9))
        fade_sub   = max(0.0, min(1.0, (t - 1.2) / 0.9))

        # ── logo: cloud halo + gold bolt ───────────────────────────────
        if fade_logo > 0:
            # cloud halo
            R = 130
            rg = cairo.RadialGradient(cx, cy, 0, cx, cy, R*1.4)
            rg.add_color_stop_rgba(0.0, 0.95, 0.98, 1.0, 0.55*fade_logo)
            rg.add_color_stop_rgba(1.0, 0.3, 0.5, 0.9, 0.0)
            cr.set_source(rg)
            cr.arc(cx, cy, R*1.4, 0, 2*math.pi); cr.fill()
            # bolt path (stylized zigzag)
            bolt = [
                (cx-8,  cy-90),
                (cx+22, cy-25),
                (cx-6,  cy-20),
                (cx+18, cy+45),
                (cx-30, cy-5),
                (cx-2,  cy-10),
                (cx-22, cy-70),
            ]
            # halo passes
            cr.set_line_cap(cairo.LINE_CAP_ROUND); cr.set_line_join(cairo.LINE_JOIN_ROUND)
            for w_px, rgba in [
                (22, (1.0, 0.85, 0.40, 0.20*fade_logo)),
                (12, (1.0, 0.88, 0.45, 0.55*fade_logo)),
                (5,  (1.0, 0.95, 0.70, 0.95*fade_logo)),
            ]:
                cr.set_source_rgba(*rgba); cr.set_line_width(w_px)
                cr.move_to(*bolt[0])
                for p in bolt[1:]: cr.line_to(*p)
                cr.stroke()

        # Title text via Pango
        try:
            from gi.repository import Pango, PangoCairo
        except Exception:
            return

        def text(cr, text, size_pt, y, alpha, weight=900, letter_em=0.15,
                 color=(0.96, 0.99, 1.0), shadow=(0.40, 0.65, 1.00, 0.55)):
            if alpha <= 0: return
            layout = PangoCairo.create_layout(cr)
            desc = Pango.FontDescription()
            desc.set_family("Inter, Cantarell, sans-serif")
            desc.set_weight(Pango.Weight.HEAVY)
            desc.set_absolute_size(size_pt * Pango.SCALE)
            layout.set_font_description(desc)
            attrs = Pango.AttrList()
            try:
                la = Pango.attr_letter_spacing_new(int(letter_em * size_pt * 1024))
                attrs.insert(la)
            except Exception:
                pass
            layout.set_attributes(attrs)
            layout.set_text(text, -1)
            w, h = layout.get_pixel_size()
            x = (width - w)/2
            # shadow / glow
            sr, sg, sb, sa = shadow
            for ox, oy, a_mult in [(0,0,1.0), (0,2,0.5), (2,0,0.4), (-2,0,0.4)]:
                cr.set_source_rgba(sr, sg, sb, sa*alpha*a_mult*0.5)
                cr.move_to(x+ox, y+oy); PangoCairo.show_layout(cr, layout)
            cr.set_source_rgba(*color, alpha)
            cr.move_to(x, y); PangoCairo.show_layout(cr, layout)

        text(cr, __app_name__.upper(), 64, height/2 + 70, fade_title, letter_em=0.32)
        text(cr, "MOUNT OLYMPUS", 18, height/2 + 160, fade_sub, letter_em=0.55,
             color=(1.0, 0.85, 0.45), shadow=(1.0, 0.75, 0.30, 0.5))
        text(cr, f"v{__version__}  ·  Joseph Sierengowski", 11, height/2 + 200,
             fade_sub*0.75, letter_em=0.30,
             color=(0.85, 0.90, 1.0), shadow=(0.4, 0.6, 1.0, 0.3))

        # Strike-synchronised announcement — appears the instant a bolt fires
        # and fades out by the next strike, naming the real boot step.
        ann = self._current_announcement(now)
        if ann is not None:
            head, sub, a = ann
            # Headline: BIG bright gold, near the bottom of the window so it
            # never collides with the centered logo/title block.
            text(cr, head, 28, height - 145, a, letter_em=0.45,
                 color=(1.0, 0.92, 0.62),
                 shadow=(1.0, 0.70, 0.25, 0.65))
            text(cr, sub, 13, height - 100, a*0.90, letter_em=0.30,
                 color=(0.92, 0.96, 1.0),
                 shadow=(0.30, 0.55, 1.0, 0.45))
        text(cr, "PRESS SPACE OR CLICK TO ENTER", 9, height - 50, 0.55,
             letter_em=0.45, color=(0.7, 0.78, 0.95),
             shadow=(0.0, 0.0, 0.0, 0.0))

    # ── shutdown ────────────────────────────────────────────────────────
    def _finish(self) -> None:
        if self._done_called:
            return
        self._done_called = True
        try:
            self.close()
        except Exception:
            pass
        cb = self._on_done
        if cb:
            try:
                cb()
            except Exception:
                log.exception("splash on_done failed")

    def set_done_callback(self, cb) -> None:
        self._on_done = cb

    def set_progress(self, text: str) -> None:
        # Kept for API parity; phase labels are driven by the storm timeline now.
        pass


# ── public entry ────────────────────────────────────────────────────────
def show_splash(app: Adw.Application, *, on_done=lambda: None, **_legacy) -> SplashWindow:
    splash = SplashWindow(app)
    splash.set_done_callback(on_done)
    splash.present()
    # Fire thunder timed to the storm schedule above.
    try:
        play_async("thunder.wav")
    except Exception:
        log.exception("thunder playback failed")
    return splash
