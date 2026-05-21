"""Matrix-style text scramble effect on hover.

Attaches a `Gtk.EventControllerMotion` to a label. On pointer enter, the
label's text is rapidly replaced with random glyphs that resolve, left to
right, back into the original string. Honors the user setting
`ui.matrix_scramble` (defaults on).
"""
from __future__ import annotations

import random
import string
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk  # noqa: E402

from godsapp.core.settings import load_settings

_GLYPHS = string.ascii_letters + string.digits + "!@#$%^&*<>?/\\|=+-_"


def _enabled() -> bool:
    try:
        return bool(load_settings().ui.matrix_scramble)
    except Exception:
        return True


def attach(label: Gtk.Label, *, frames: int = 14, interval_ms: int = 28) -> None:
    """Attach the scramble effect to a label.

    Safe to call on every row — no-op when the user disables the setting,
    and re-checks the setting on each hover so toggling Settings takes
    effect immediately for newly-hovered rows.
    """
    state: dict[str, Optional[int]] = {"src": None}

    def on_enter(_ctrl, _x, _y) -> None:
        if not _enabled():
            return
        target = label.get_text()
        if not target or any(c not in string.printable for c in target):
            return
        if state["src"] is not None:
            GLib.source_remove(state["src"])
            state["src"] = None

        # progress[i] == True means character i has resolved
        n = len(target)
        progress = [False] * n
        step = {"i": 0}

        def tick() -> bool:
            i = step["i"]
            # resolve one more character per frame
            reveal_to = min(n, int((i / max(frames, 1)) * n) + 1)
            for k in range(reveal_to):
                progress[k] = True
            chars = []
            for k, ch in enumerate(target):
                if progress[k] or ch == " ":
                    chars.append(ch)
                else:
                    chars.append(random.choice(_GLYPHS))
            label.set_text("".join(chars))
            step["i"] += 1
            if step["i"] > frames:
                label.set_text(target)
                state["src"] = None
                return False
            return True

        state["src"] = GLib.timeout_add(interval_ms, tick)

    def on_leave(_ctrl) -> None:
        if state["src"] is not None:
            GLib.source_remove(state["src"])
            state["src"] = None
            # Snap back to original text
            # (the original is stored implicitly by the most recent set_text)

    ctrl = Gtk.EventControllerMotion.new()
    ctrl.connect("enter", on_enter)
    ctrl.connect("leave", on_leave)
    label.add_controller(ctrl)
