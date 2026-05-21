"""Lightweight audio playback for splash/event sounds.

Tries the most likely backends in order and falls back to silence. Never
blocks the GTK main loop — playback is fire-and-forget via subprocess.
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
        # importlib.resources Traversable -> use str path; it's a real file on disk
        path = Path(str(p))
        if path.exists():
            return path
    except Exception:
        log.exception("audio resource resolve failed: %s", name)
    return None


def _player_cmd() -> list[str] | None:
    """Pick the first available system audio player."""
    for cmd in (
        ["paplay"],                     # PulseAudio / PipeWire-pulse
        ["pw-play"],                    # PipeWire native
        ["aplay", "-q"],                # ALSA
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
        ["mpv", "--really-quiet", "--no-video"],
    ):
        if shutil.which(cmd[0]):
            return cmd
    return None


def play_async(name: str) -> None:
    """Play a bundled sound by filename (e.g. 'thunder.wav'). Non-blocking."""
    try:
        if not load_settings().ui.sounds_enabled:
            return
    except Exception:
        pass  # if settings haven't loaded yet, default to playing
    path = _resolve(name)
    if path is None:
        return
    cmd = _player_cmd()
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
