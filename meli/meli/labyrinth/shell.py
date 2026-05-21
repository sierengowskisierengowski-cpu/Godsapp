"""
Per-connection fake shell session for the Labyrinth tarpit.

`LabyrinthSession` owns one trapped attacker: their procedurally
generated filesystem, command history, identity, and the asyncio
reader/writer pair into their socket. It runs a small read-execute-
respond loop that mimics a real bash session well enough to satisfy
brute-force botnets and casual humans.

Login is intentionally permissive: every credential succeeds. We log
every attempt anyway so the Credentials view fills up with what
attackers are trying.
"""
from __future__ import annotations

import asyncio
import shlex
import time
from dataclasses import dataclass, field

import structlog

from meli.labyrinth.commands import COMMANDS, unknown_response
from meli.labyrinth.filesystem import FakeFS, new_session_seed
from meli.labyrinth import sink

log = structlog.get_logger()


# Telnet negotiation: we send WILL ECHO + WILL SUPPRESS-GO-AHEAD and DO
# DON't on the basics. Most Mirai-family bots ignore negotiation entirely;
# real telnet clients handle it correctly. We don't need full RFC 854 —
# enough to look real and not crash the bot's parser.
IAC  = bytes([255])
WILL = bytes([251])
WONT = bytes([252])
DO   = bytes([253])
DONT = bytes([254])
SB   = bytes([250])
SE   = bytes([240])

OPT_ECHO       = bytes([1])
OPT_SUPPRESS_GA = bytes([3])
OPT_TERMINAL_TYPE = bytes([24])
OPT_NAWS = bytes([31])

# Telnet line ending — be liberal in what we accept (\r\n, \r\0, \n).
_TELNET_EOLS = (b"\r\n", b"\r\0", b"\n", b"\r")


@dataclass
class LabyrinthSession:
    session_id: str
    peer_ip: str
    peer_port: int
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    username: str = ""
    password: str = ""
    command_history: list[str] = field(default_factory=list)
    requested_exit: bool = False
    start_ts: float = field(default_factory=time.monotonic)
    fs: FakeFS = field(default_factory=lambda: FakeFS(session_seed=new_session_seed()))

    # ---- IO primitives ------------------------------------------------

    async def send(self, text: str) -> None:
        try:
            self.writer.write(text.encode("utf-8", errors="replace"))
            await self.writer.drain()
        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            raise
        except Exception as e:
            log.debug("labyrinth send failed", error=str(e), session=self.session_id)

    async def send_bytes(self, data: bytes) -> None:
        try:
            self.writer.write(data)
            await self.writer.drain()
        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            raise
        except Exception:
            pass

    async def read_line(self, timeout: float = 600.0) -> str | None:
        """Read one CRLF-terminated line, stripping telnet IAC sequences.

        Returns None on EOF / timeout / disconnect.
        """
        try:
            data = await asyncio.wait_for(self._read_raw_line(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        except (ConnectionResetError, asyncio.IncompleteReadError):
            return None
        if data is None:
            return None
        cleaned = _strip_telnet(data)
        # Strip every recognized EOL terminator
        for eol in _TELNET_EOLS:
            if cleaned.endswith(eol):
                cleaned = cleaned[: -len(eol)]
                break
        try:
            return cleaned.decode("utf-8", errors="replace").rstrip()
        except Exception:
            return ""

    async def _read_raw_line(self) -> bytes | None:
        # readuntil("\n") catches both \r\n and bare \n. The asyncio
        # StreamReader limit is 8KiB (set by the daemon); going over
        # means an attacker pasted >8KiB without a newline. We must
        # drain to the next real newline (or EOF) to resync — otherwise
        # the bytes stay in the buffer and the next readuntil immediately
        # raises again in a tight loop, generating fake "commands" per
        # 8KiB chunk and feeding the sink queue from a malformed stream.
        try:
            return await self.reader.readuntil(b"\n")
        except asyncio.LimitOverrunError as e:
            # Discard the oversized prefix, capped so a flood can't
            # consume unbounded CPU. After the cap we just close the
            # session — a legitimate user does not send 1MB of unbroken
            # bytes to a login shell.
            discarded = 0
            DRAIN_CAP = 1 * 1024 * 1024  # 1 MiB
            CHUNK = 8 * 1024
            while discarded < DRAIN_CAP:
                # consumed tells us how many bytes are in the buffer up
                # to (but not including) any newline match. Consume them.
                to_drop = min(e.consumed, CHUNK)
                if to_drop <= 0:
                    to_drop = CHUNK
                try:
                    await self.reader.readexactly(to_drop)
                except asyncio.IncompleteReadError:
                    return None
                discarded += to_drop
                try:
                    return await self.reader.readuntil(b"\n")
                except asyncio.LimitOverrunError as e2:
                    e = e2
                    continue
                except asyncio.IncompleteReadError:
                    return None
            log.debug("labyrinth session sent oversized stream — closing",
                      session=self.session_id, peer_ip=self.peer_ip,
                      discarded=discarded)
            return None
        except asyncio.IncompleteReadError as e:
            return e.partial if e.partial else None

    # ---- main loop ----------------------------------------------------

    async def run(self) -> None:
        sink.emit_connect(self.session_id, self.peer_ip, self.peer_port)
        try:
            await self._negotiate_telnet()
            if not await self._fake_login():
                return
            await self._command_loop()
        finally:
            duration = time.monotonic() - self.start_ts
            sink.emit_disconnect(
                self.session_id, self.peer_ip, duration, len(self.command_history)
            )
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass

    async def _negotiate_telnet(self) -> None:
        # Tell the client: we'll handle echo, suppress go-ahead. Tell
        # them: don't echo on their side, send terminal type + window
        # size if they want. (We ignore their responses.)
        await self.send_bytes(IAC + WILL + OPT_ECHO)
        await self.send_bytes(IAC + WILL + OPT_SUPPRESS_GA)
        await self.send_bytes(IAC + DO + OPT_SUPPRESS_GA)
        await self.send_bytes(IAC + DONT + OPT_ECHO)

    async def _fake_login(self) -> bool:
        # Realistic banner + login prompt. Most Mirai variants expect
        # exactly "login:" and "Password:" with these capitalisations.
        await self.send("\r\nUbuntu 22.04.3 LTS ubuntu-prod-01\r\n\r\n")

        for attempt in range(3):
            await self.send("ubuntu-prod-01 login: ")
            user = await self.read_line(timeout=120.0)
            if user is None:
                return False
            await self.send("Password: ")
            pwd = await self.read_line(timeout=120.0)
            if pwd is None:
                return False

            # Always succeed — but only on attempts 1+ so it looks more
            # realistic. (First attempt usually "fails" for attackers
            # probing the prompt; rest succeed.)
            if attempt == 0 and (not user or not pwd):
                await self.send("\r\nLogin incorrect\r\n\r\n")
                sink.emit_login(self.session_id, self.peer_ip, user or "", pwd or "", False)
                continue

            self.username = (user or "root").strip()
            self.password = (pwd or "").strip()
            self.fs.home = "/root" if self.username == "root" else f"/home/{self.username}"
            self.fs.cwd  = self.fs.home
            sink.emit_login(self.session_id, self.peer_ip, self.username, self.password, True)

            # MOTD + first prompt
            await self.send(
                "\r\nWelcome to Ubuntu 22.04.3 LTS (GNU/Linux 5.15.0-91-generic x86_64)\r\n\r\n"
                " * Documentation:  https://help.ubuntu.com\r\n"
                " * Management:     https://landscape.canonical.com\r\n"
                " * Support:        https://ubuntu.com/advantage\r\n\r\n"
                "Last login: " + _fake_last_login() + "\r\n"
            )
            return True
        return False

    async def _command_loop(self) -> None:
        while not self.requested_exit:
            await self.send(self._prompt())
            line = await self.read_line(timeout=900.0)  # 15 min idle limit
            if line is None:
                return
            line = line.strip()
            if not line:
                continue
            self.command_history.append(line)
            sink.emit_command(self.session_id, self.peer_ip, line)
            await self._dispatch(line)

    async def _dispatch(self, line: str) -> None:
        # Split on shell-like whitespace, tolerate quoting errors
        try:
            tokens = shlex.split(line, posix=True)
        except ValueError:
            tokens = line.split()
        if not tokens:
            return

        # Handle simple shell pipelines / semicolons by running the first
        # command only. Real bash would run them all, but for tarpit
        # purposes the response only needs to look plausible — and most
        # attacker one-liners don't care about output of later stages.
        for sep in (";", "&&", "||", "|"):
            if sep in tokens:
                tokens = tokens[: tokens.index(sep)]
                if not tokens:
                    return

        cmd_name = tokens[0]
        args = tokens[1:]
        handler = COMMANDS.get(cmd_name)
        if handler is None:
            # Common shell-builtins-ish that botnets try
            if cmd_name in ("sudo", "su"):
                # Pretend it worked silently — they're already "root" anyway
                if args:
                    sub = COMMANDS.get(args[0])
                    if sub is not None:
                        await self.send(sub(self, args[1:]))
                        return
            await self.send(unknown_response(cmd_name))
            return
        try:
            output = handler(self, args)
        except Exception as e:
            log.debug("labyrinth command crashed", cmd=cmd_name, error=str(e))
            output = unknown_response(cmd_name)
        if output:
            await self.send(output)

    def _prompt(self) -> str:
        # bash-style PS1: user@host:cwd$ — root gets #, others get $
        sym = "#" if self.username == "root" else "$"
        cwd_disp = self.fs.cwd if self.fs.cwd != self.fs.home else "~"
        return f"{self.username}@ubuntu-prod-01:{cwd_disp}{sym} "


# ── helpers ─────────────────────────────────────────────────────────────


def _strip_telnet(data: bytes) -> bytes:
    """Remove inline telnet IAC command sequences from a byte buffer."""
    if IAC not in data:
        return data
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b != 255:  # IAC
            out.append(b)
            i += 1
            continue
        # IAC sequence: at minimum IAC + cmd (+ option). Subnegotiation
        # is IAC SB ... IAC SE.
        if i + 1 >= n:
            i += 1
            continue
        cmd = data[i + 1]
        if cmd == 250:  # SB ... SE — scan to IAC SE
            j = i + 2
            while j < n - 1:
                if data[j] == 255 and data[j + 1] == 240:
                    i = j + 2
                    break
                j += 1
            else:
                return bytes(out)
            continue
        if cmd in (251, 252, 253, 254):  # WILL/WONT/DO/DONT have one option byte
            i += 3
            continue
        # Other 2-byte commands
        i += 2
    return bytes(out)


def _fake_last_login() -> str:
    from datetime import datetime, timedelta, timezone
    t = datetime.now(timezone.utc) - timedelta(hours=14, minutes=23)
    return t.strftime("%a %b %d %H:%M:%S %Y from 10.0.0.42")
