"""
Asyncio TCP Telnet daemon for the Labyrinth tarpit.

The daemon runs on its own background thread with a dedicated asyncio
event loop, so it can coexist cleanly with Meli's GTK main loop. Each
accepted connection spawns a `LabyrinthSession` coroutine; sessions
are tracked in a set so the UI can ask "how many attackers are trapped
right now?" and so we can cleanly cancel everyone on stop().

Configurable via the standard meli.config:
  labyrinth.enabled         (bool,  default False — opt in)
  labyrinth.bind_host       (str,   default "0.0.0.0")
  labyrinth.bind_port       (int,   default 2323)
  labyrinth.max_sessions    (int,   default 200 — refuse beyond this)
"""
from __future__ import annotations

import asyncio
import threading

import structlog

from meli.labyrinth.shell import LabyrinthSession
from meli.labyrinth import sink

log = structlog.get_logger()


class LabyrinthDaemon:
    """Background-threaded asyncio Telnet tarpit server.

    Lifecycle:
        d = LabyrinthDaemon(host=..., port=..., max_sessions=...)
        d.start()       # non-blocking; spawns thread + loop
        d.session_count()
        d.stop(timeout=5.0)
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 2323,
        max_sessions: int = 200,
        taunt_intensity: str = "full",
    ) -> None:
        self.host = host
        self.port = port
        self.max_sessions = max(1, int(max_sessions))
        # Normalise: anything unrecognised falls back to "full" since
        # that's the design default (HA HA gotcha personality). Log a
        # warning so operators editing config.toml notice their typo.
        if taunt_intensity not in ("off", "subtle", "full"):
            log.warning("Labyrinth taunt_intensity unrecognised, defaulting to 'full'",
                        provided=taunt_intensity)
            taunt_intensity = "full"
        self.taunt_intensity = taunt_intensity

        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: asyncio.base_events.Server | None = None
        self._sessions: set[asyncio.Task] = set()
        self._sessions_lock = threading.Lock()
        self._running = threading.Event()
        self._stopped = threading.Event()
        self._stopped.set()

    # ---- public API ---------------------------------------------------

    def start(self) -> bool:
        """Start the daemon thread. Returns True if the asyncio server
        bound successfully within the timeout, False otherwise (e.g.
        port already in use). On False the daemon is fully cleaned up.
        """
        if self._thread is not None and self._thread.is_alive():
            return self.is_running()
        self._stopped.clear()
        self._running.clear()
        self._thread = threading.Thread(
            target=self._thread_main,
            name="meli-labyrinth",
            daemon=True,
        )
        self._thread.start()
        # Wait for either successful bind (running) or early thread exit.
        deadline_steps = 30  # 30 * 0.1s = 3s
        for _ in range(deadline_steps):
            if self._running.is_set():
                return True
            if not self._thread.is_alive():
                self._stopped.set()
                return False
            if self._stopped.is_set():
                return False
            import time
            time.sleep(0.1)
        return self._running.is_set()

    def stop(self, timeout: float = 5.0) -> bool:
        """Signal the server to shut down and wait for the worker thread
        to actually exit. Returns True on clean shutdown, False on
        timeout (in which case the thread is still alive somewhere
        unwinding — the caller should NOT report a successful stop).
        """
        if self._stopped.is_set() and (self._thread is None or not self._thread.is_alive()):
            return True
        loop = self._loop
        if loop is not None:
            try:
                loop.call_soon_threadsafe(self._shutdown_signal)
            except RuntimeError:
                # Loop already closed
                pass
        # Wait for the loop to flip _stopped (set in _thread_main finally).
        clean = self._stopped.wait(timeout=timeout)
        # Then join the actual thread so we don't leave it half-alive.
        if self._thread is not None:
            self._thread.join(timeout=max(0.5, timeout))
            if self._thread.is_alive():
                return False
        return clean

    def is_running(self) -> bool:
        return self._running.is_set() and not self._stopped.is_set()

    def session_count(self) -> int:
        with self._sessions_lock:
            return sum(1 for t in self._sessions if not t.done())

    # ---- internal -----------------------------------------------------

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._serve())
        except Exception as e:
            log.error("labyrinth daemon crashed", error=str(e))
        finally:
            self._running.clear()
            self._stopped.set()

    async def _serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        try:
            self._server = await asyncio.start_server(
                self._handle_connection, self.host, self.port,
                # Cap one line at 8 KiB — discourages buffer-bomb attacks
                limit=8 * 1024,
            )
        except OSError as e:
            log.error("labyrinth bind failed", host=self.host, port=self.port, error=str(e))
            return

        log.info("labyrinth listening", host=self.host, port=self.port,
                 max_sessions=self.max_sessions)
        self._running.set()
        try:
            async with self._server:
                await self._server.serve_forever()
        except asyncio.CancelledError:
            pass
        finally:
            # Cancel every in-flight session so the loop can exit cleanly.
            with self._sessions_lock:
                tasks = [t for t in self._sessions if not t.done()]
            for t in tasks:
                t.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    def _shutdown_signal(self) -> None:
        """Called via call_soon_threadsafe from stop() — runs on the loop."""
        if self._server is not None:
            self._server.close()
        # serve_forever() unwinds on close(); the cleanup is in _serve.

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peer = writer.get_extra_info("peername") or ("0.0.0.0", 0)
        peer_ip = str(peer[0]) if peer else "0.0.0.0"
        peer_port = int(peer[1]) if peer and len(peer) > 1 else 0

        # Concurrency cap — refuse politely if we're already full.
        with self._sessions_lock:
            active = sum(1 for t in self._sessions if not t.done())
        if active >= self.max_sessions:
            try:
                writer.write(b"\r\nSystem busy, try again later.\r\n")
                await writer.drain()
            except Exception:
                pass
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            return

        from meli.labyrinth.taunts import TauntEngine
        session = LabyrinthSession(
            session_id=sink.new_session_id(),
            peer_ip=peer_ip,
            peer_port=peer_port,
            reader=reader,
            writer=writer,
            taunts=TauntEngine(intensity=self.taunt_intensity),
        )
        task = asyncio.current_task()
        with self._sessions_lock:
            if task is not None:
                self._sessions.add(task)
        try:
            await session.run()
        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            pass
        except Exception as e:
            log.debug("labyrinth session error", error=str(e), peer_ip=peer_ip)
        finally:
            with self._sessions_lock:
                if task is not None:
                    self._sessions.discard(task)
