"""Lightweight audio playback for splash/event sounds.

Tries the most likely backends in order and falls back to silence. Never
blocks the GTK main loop — playback is fire-and-forget via subprocess.
Per-call `volume` (0.0–1.0) is honoured when the backend supports it.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from godsapp.core.logging import get_logger
from godsapp.core.settings import load_settings

log = get_logger(__name__)


def _resolve(name: str) -> Path | None:
    try:
        from importlib.resources import files
        p = files("godsapp.resources.audio").joinpath(name)
        path = Path(str(p))
        if path.exists():
            return path
    except Exception:
        log.exception("audio resource resolve failed: %s", name)
    return None


def _player_cmd(volume: float) -> list[str] | None:
    """Pick the first available system audio player, with backend-native
    volume flags injected when supported. `volume` is a 0.0–1.0 fraction."""
    v = max(0.0, min(1.0, float(volume)))
    # paplay: --volume in 0..65536 (65536 = 100%)
    if shutil.which("paplay"):
        return ["paplay", f"--volume={int(v*65536)}"]
    # pw-play: --volume in 0.0..1.0
    if shutil.which("pw-play"):
        return ["pw-play", f"--volume={v:.3f}"]
    # ffplay: -volume in 0..100
    if shutil.which("ffplay"):
        return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
                "-volume", str(int(v*100))]
    # mpv: --volume in 0..100 (capped at 100 by default)
    if shutil.which("mpv"):
        return ["mpv", "--really-quiet", "--no-video", f"--volume={int(v*100)}"]
    # aplay: no volume flag — falls back to system mixer level
    if shutil.which("aplay"):
        return ["aplay", "-q"]
    return None


def play_async(name: str, *, volume: float = 1.0) -> None:
    """Play a bundled sound by filename. Non-blocking.

    `volume` is a 0.0–1.0 multiplier applied at the backend level when the
    underlying player supports it (paplay/pw-play/ffplay/mpv all do; aplay
    falls through silently to system mixer level).
    """
    try:
        if not load_settings().ui.sounds_enabled:
            return
    except Exception:
        pass
    path = _resolve(name)
    if path is None:
        return
    cmd = _player_cmd(volume)
    if cmd is None:
        return
    try:
        subprocess.Popen(
            cmd + [str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        log.exception("audio play failed: %s", name)
