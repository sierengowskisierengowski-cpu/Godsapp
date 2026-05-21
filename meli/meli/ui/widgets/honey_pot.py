"""
Honey-pot centerpiece widget.

A Cairo-drawn jar that fills with honey as events accumulate, pulses
when new events arrive, and emits drips down the side (continuously
when the pot is overflowing).

The same shape is reused as the app logo — see ``logo_svg()`` for a
small SVG export suitable for the headerbar.
"""
from __future__ import annotations

import math
import random
import time

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib  # noqa: E402

import cairo  # noqa: E402

# Palette — keep in sync with resources/css/style.css
HIVE_BLACK   = (0x10/255, 0x0a/255, 0x04/255)
COMB_PANEL   = (0x22/255, 0x1a/255, 0x12/255)
RAW_HONEY    = (0xd4/255, 0xa0/255, 0x17/255)
AMBER_GLOW   = (0xf5/255, 0x9e/255, 0x0b/255)
DARK_HONEY   = (0x8a/255, 0x5d/255, 0x05/255)
PALE_COMB    = (0xfe/255, 0xf3/255, 0xc7/255)
WARM_BORDER  = (0x3a/255, 0x28/255, 0x18/255)
STING_RED    = (0xdc/255, 0x26/255, 0x26/255)

FRAME_MS = 33  # ~30 fps


class Drip:
    """A single honey drip running down the outside of the jar."""
    __slots__ = ("x", "y", "vy", "born", "lifetime", "size")

    def __init__(self, x: float, y: float, size: float = 4.0, lifetime: float = 1.4):
        self.x = x
        self.y = y
        self.vy = 18.0      # px/sec, accelerates with gravity
        self.born = time.monotonic()
        self.lifetime = lifetime
        self.size = size

    def alive(self) -> bool:
        return (time.monotonic() - self.born) < self.lifetime

    def advance(self, dt: float) -> None:
        self.vy += 35.0 * dt
        self.y += self.vy * dt


class HoneyPotWidget(Gtk.DrawingArea):
    """Centerpiece honey-pot widget. Public API:

        set_event_count(n)   — animates fill level toward log-scaled target
        pulse(severity)      — one-shot glow + drip on the rim
        set_max_events(n)    — change the "100% full" threshold
    """

    def __init__(self, max_events: int = 10000):
        super().__init__()
        self.set_size_request(220, 260)
        self.set_content_width(220)
        self.set_content_height(260)
        self.set_draw_func(self._draw)

        self._max_events = max(1, max_events)
        self._target_fill = 0.0       # 0..1
        self._current_fill = 0.0
        self._event_count = 0

        self._drips: list[Drip] = []
        self._pulse_until = 0.0       # monotonic timestamp
        self._pulse_color = AMBER_GLOW
        self._wobble_phase = random.random() * math.tau
        self._overflow_accumulator = 0.0
        self._last_frame = time.monotonic()

        GLib.timeout_add(FRAME_MS, self._tick)

    # ── Public ─────────────────────────────────────────────────────────

    def set_event_count(self, n: int) -> None:
        self._event_count = max(0, int(n))
        # Logarithmic fill: feels alive even at low counts, still has
        # room to grow at high volume. n=10 → ~30%, n=100 → ~50%,
        # n=max → 100%.
        if self._event_count == 0:
            self._target_fill = 0.0
        else:
            self._target_fill = min(
                1.0,
                math.log10(self._event_count + 1) / math.log10(self._max_events + 1),
            )

    def set_max_events(self, n: int) -> None:
        self._max_events = max(1, int(n))
        self.set_event_count(self._event_count)

    def pulse(self, severity: str = "INFO") -> None:
        sev = (severity or "INFO").upper()
        if sev == "CRITICAL":
            self._pulse_color = STING_RED
            duration = 1.0
        elif sev == "HIGH":
            self._pulse_color = AMBER_GLOW
            duration = 0.7
        else:
            self._pulse_color = RAW_HONEY
            duration = 0.5
        self._pulse_until = time.monotonic() + duration
        # Spawn a celebratory drip from the rim
        self._spawn_drip_at_rim()

    # ── Animation loop ─────────────────────────────────────────────────

    def _tick(self) -> bool:
        now = time.monotonic()
        dt = now - self._last_frame
        self._last_frame = now

        # Ease current fill toward target
        delta = self._target_fill - self._current_fill
        if abs(delta) > 0.001:
            self._current_fill += delta * min(1.0, dt * 2.2)

        # Wobble phase
        self._wobble_phase = (self._wobble_phase + dt * 1.6) % math.tau

        # Continuous overflow drips when full
        if self._current_fill >= 0.98:
            self._overflow_accumulator += dt
            if self._overflow_accumulator > 0.45:  # ~2 drips/sec
                self._overflow_accumulator = 0.0
                self._spawn_drip_at_rim()

        # Age drips
        for d in self._drips:
            d.advance(dt)
        self._drips = [d for d in self._drips if d.alive() and d.y < 260]

        self.queue_draw()
        return True  # keep ticking

    def _spawn_drip_at_rim(self) -> None:
        # Drip slides down one side of the neck. Pick left or right.
        side = random.choice((-1, 1))
        # Rim x position relative to center (matches _draw geometry)
        x_center = 110
        rim_offset = 38
        x = x_center + side * (rim_offset - random.uniform(2, 6))
        y = 86 + random.uniform(0, 4)  # just below the rim
        self._drips.append(Drip(x, y, size=random.uniform(3.0, 5.5)))

    # ── Drawing ────────────────────────────────────────────────────────

    def _draw(self, area, cr: cairo.Context, width: int, height: int) -> None:
        cx = width / 2
        # Geometry: tall jar with rounded shoulders, shorter neck, lip.
        # All coordinates are in widget-local pixels.
        rim_top_y    = 80
        rim_bot_y    = 92
        neck_w       = 38   # half-width
        shoulder_y   = 110
        body_top_y   = 130
        body_w       = 78   # half-width at widest
        body_bot_y   = 232
        base_y       = 240
        base_w       = 60   # half-width

        # ── Pulse glow halo behind the jar ──────────────────────────
        now = time.monotonic()
        if now < self._pulse_until:
            remaining = self._pulse_until - now
            fade = max(0.0, min(1.0, remaining / 0.5))
            for i in range(4, 0, -1):
                radius = body_w + 18 + i * 8
                alpha = 0.14 * fade / i
                grad = cairo.RadialGradient(cx, 180, body_w * 0.4, cx, 180, radius)
                grad.add_color_stop_rgba(0, *self._pulse_color, alpha)
                grad.add_color_stop_rgba(1, *self._pulse_color, 0)
                cr.set_source(grad)
                cr.arc(cx, 180, radius, 0, math.tau)
                cr.fill()

        # ── Jar silhouette path (used twice: clip for honey, stroke for outline) ──
        def jar_path():
            cr.new_path()
            # Start at left of rim top
            cr.move_to(cx - neck_w, rim_top_y)
            # Lip top
            cr.line_to(cx + neck_w, rim_top_y)
            # Lip right side down to neck
            cr.line_to(cx + neck_w, rim_bot_y)
            # Shoulder curve right
            cr.curve_to(
                cx + neck_w + 2, rim_bot_y + 8,
                cx + body_w, shoulder_y,
                cx + body_w, body_top_y,
            )
            # Right body straight-ish (slight curve out)
            cr.curve_to(
                cx + body_w + 2, body_top_y + 35,
                cx + body_w + 2, body_bot_y - 35,
                cx + body_w, body_bot_y,
            )
            # Bottom curve right
            cr.curve_to(
                cx + body_w - 4, body_bot_y + 5,
                cx + base_w + 4, base_y - 2,
                cx + base_w, base_y,
            )
            # Bottom edge
            cr.line_to(cx - base_w, base_y)
            # Bottom curve left
            cr.curve_to(
                cx - base_w - 4, base_y - 2,
                cx - body_w + 4, body_bot_y + 5,
                cx - body_w, body_bot_y,
            )
            # Left body up
            cr.curve_to(
                cx - body_w - 2, body_bot_y - 35,
                cx - body_w - 2, body_top_y + 35,
                cx - body_w, body_top_y,
            )
            # Shoulder curve left up to neck
            cr.curve_to(
                cx - body_w, shoulder_y,
                cx - neck_w - 2, rim_bot_y + 8,
                cx - neck_w, rim_bot_y,
            )
            # Up the left lip
            cr.line_to(cx - neck_w, rim_top_y)
            cr.close_path()

        # ── Jar body fill (ceramic) ─────────────────────────────────
        jar_path()
        body_grad = cairo.LinearGradient(0, rim_top_y, 0, base_y)
        body_grad.add_color_stop_rgb(0.0, *COMB_PANEL)
        body_grad.add_color_stop_rgb(0.5, 0x2c/255, 0x1f/255, 0x14/255)
        body_grad.add_color_stop_rgb(1.0, *WARM_BORDER)
        cr.set_source(body_grad)
        cr.fill_preserve()
        # Soft inner highlight on the left shoulder
        hl = cairo.LinearGradient(cx - body_w, 0, cx + body_w, 0)
        hl.add_color_stop_rgba(0, *PALE_COMB, 0.06)
        hl.add_color_stop_rgba(0.4, *PALE_COMB, 0)
        cr.set_source(hl)
        cr.fill()

        # ── Honey fill (clipped to jar path) ────────────────────────
        cr.save()
        jar_path()
        cr.clip()

        # Honey surface y: interpolate from base (empty) to rim_bot_y (full)
        fill = max(0.0, min(1.0, self._current_fill))
        # Restrict honey to the body cavity (don't fill the neck unless overflowing)
        empty_y = base_y - 6
        full_y = rim_bot_y + 4
        surface_y = empty_y + (full_y - empty_y) * fill

        # Wobble: low-amplitude sine across surface, gives a liquid feel
        wob_amp = 1.6 if fill > 0.05 else 0
        steps = 32
        cr.new_path()
        cr.move_to(cx - body_w - 6, base_y + 4)
        for i in range(steps + 1):
            t = i / steps
            x = (cx - body_w - 6) + t * (body_w * 2 + 12)
            y = surface_y + math.sin(self._wobble_phase + t * math.tau * 1.5) * wob_amp
            cr.line_to(x, y)
        cr.line_to(cx + body_w + 6, base_y + 4)
        cr.close_path()

        honey_grad = cairo.LinearGradient(0, surface_y, 0, base_y)
        honey_grad.add_color_stop_rgba(0.0, *AMBER_GLOW, 0.95)
        honey_grad.add_color_stop_rgba(0.5, *RAW_HONEY, 1.0)
        honey_grad.add_color_stop_rgba(1.0, *DARK_HONEY, 1.0)
        cr.set_source(honey_grad)
        cr.fill()

        # Specular highlight stripe on the honey
        if fill > 0.05:
            cr.set_source_rgba(*PALE_COMB, 0.18)
            cr.set_line_width(2)
            cr.move_to(cx - body_w * 0.5, surface_y + 6)
            cr.line_to(cx - body_w * 0.1, surface_y + 4)
            cr.stroke()

        cr.restore()

        # ── Jar outline ─────────────────────────────────────────────
        jar_path()
        cr.set_source_rgb(*RAW_HONEY)
        cr.set_line_width(2.2)
        cr.stroke()

        # Lip detail
        cr.set_source_rgba(*RAW_HONEY, 0.7)
        cr.set_line_width(1.4)
        cr.move_to(cx - neck_w, rim_bot_y)
        cr.line_to(cx + neck_w, rim_bot_y)
        cr.stroke()

        # ── Drips on the outside ────────────────────────────────────
        for d in self._drips:
            # Teardrop shape: tail + bulb
            age = (time.monotonic() - d.born) / d.lifetime
            alpha = 1.0 - age * 0.4
            cr.set_source_rgba(*RAW_HONEY, alpha)
            cr.new_path()
            # Tail
            cr.move_to(d.x - d.size * 0.3, d.y - d.size * 1.8)
            cr.line_to(d.x + d.size * 0.3, d.y - d.size * 1.8)
            cr.line_to(d.x + d.size * 0.6, d.y - d.size * 0.5)
            cr.arc(d.x, d.y, d.size * 0.9, 0, math.tau)
            cr.line_to(d.x - d.size * 0.6, d.y - d.size * 0.5)
            cr.close_path()
            cr.fill()
            # Highlight dot
            cr.set_source_rgba(*PALE_COMB, alpha * 0.5)
            cr.arc(d.x - d.size * 0.25, d.y - d.size * 0.25, d.size * 0.25, 0, math.tau)
            cr.fill()

        # ── Count label below the pot ───────────────────────────────
        cr.set_source_rgb(*PALE_COMB)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(13)
        label = f"{self._event_count:,} caught"
        extents = cr.text_extents(label)
        cr.move_to(cx - extents.width / 2, base_y + 22)
        cr.show_text(label)

        # Percent below
        cr.set_source_rgba(*PALE_COMB, 0.6)
        cr.set_font_size(10)
        pct = f"{int(round(fill * 100))}% full"
        ex2 = cr.text_extents(pct)
        cr.move_to(cx - ex2.width / 2, base_y + 38)
        cr.show_text(pct)


def logo_svg(size: int = 64) -> str:
    """Return a small static SVG of the honey pot — for headerbar /
    app icon use. Half-full, no drips, no animation. Renders in any
    SVG-capable widget (Gtk.Picture.new_for_filename / Gio.MemoryInputStream)."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 260" width="{size}" height="{size}">
  <defs>
    <linearGradient id="body" x1="0" y1="80" x2="0" y2="240" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#221a12"/>
      <stop offset="0.5" stop-color="#2c1f14"/>
      <stop offset="1" stop-color="#3a2818"/>
    </linearGradient>
    <linearGradient id="honey" x1="0" y1="160" x2="0" y2="240" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#f59e0b"/>
      <stop offset="0.5" stop-color="#d4a017"/>
      <stop offset="1" stop-color="#8a5d05"/>
    </linearGradient>
    <clipPath id="jarclip">
      <path d="M 72 80 L 148 80 L 148 92 C 150 100 188 110 188 130 C 190 165 190 197 188 232 C 184 237 164 238 170 240 L 50 240 C 56 238 36 237 32 232 C 30 197 30 165 32 130 C 32 110 70 100 72 92 Z"/>
    </clipPath>
  </defs>
  <!-- Jar body -->
  <path d="M 72 80 L 148 80 L 148 92 C 150 100 188 110 188 130 C 190 165 190 197 188 232 C 184 237 164 238 170 240 L 50 240 C 56 238 36 237 32 232 C 30 197 30 165 32 130 C 32 110 70 100 72 92 Z"
        fill="url(#body)" stroke="#d4a017" stroke-width="2.2"/>
  <!-- Honey fill (half) -->
  <rect x="20" y="160" width="180" height="80" fill="url(#honey)" clip-path="url(#jarclip)"/>
  <!-- Lip -->
  <line x1="72" y1="92" x2="148" y2="92" stroke="#d4a017" stroke-width="1.4" opacity="0.7"/>
  <!-- Hanging drip -->
  <path d="M 110 240 Q 108 250 110 254 Q 112 250 110 240 Z" fill="#d4a017"/>
</svg>"""
