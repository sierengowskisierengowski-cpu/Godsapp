"""
Labyrinth — Meli's native tarpit honeypot.

A Telnet (and, in v1.1, SSH) daemon that accepts every login, drops the
attacker into a procedurally-generated fake shell, and never lets them
escape into anything real. Every keystroke is logged into Meli's normal
ingest pipeline as if it came from a real Cowrie honeypot — so trapped
sessions populate the Live Feed, Commands view, Sessions view, and the
dashboard amphora automatically.

Public API:
    from meli.labyrinth import LabyrinthDaemon
    daemon = LabyrinthDaemon(host="0.0.0.0", port=2323)
    daemon.start()                          # spawns background asyncio thread
    daemon.stop()                           # graceful shutdown
    daemon.session_count() -> int           # currently trapped attackers
"""
from __future__ import annotations

from meli.labyrinth.daemon import LabyrinthDaemon

__all__ = ["LabyrinthDaemon"]
