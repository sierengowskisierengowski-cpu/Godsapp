"""Password & Hash tools — hashcat, john, hydra. Real subprocess wrappers.

`target` is interpreted as the hash file or service URL (e.g. ssh://10.0.0.1).
"""
from __future__ import annotations

import re
import shutil
from typing import Any

from godsapp.tools.base import Tool, ToolOption, ToolResult
from godsapp.tools.registry import registry


_HASH_MODES = {
    "0 - MD5": "0", "100 - SHA1": "100", "1400 - SHA-256": "1400",
    "1700 - SHA-512": "1700", "1000 - NTLM": "1000",
    "1800 - sha512crypt": "1800", "3200 - bcrypt": "3200",
    "22000 - WPA-PBKDF2": "22000", "5600 - NetNTLMv2": "5600",
}


class HashcatTool(Tool):
    name = "hashcat"
    title = "Hashcat — GPU password recovery"
    category = "password"
    description = "Crack password hashes with GPU acceleration. Target = path to hash file."
    requires_binary = "hashcat"
    options = [
        ToolOption("mode", "Hash mode (-m)", "choice",
                   default="0 - MD5", choices=list(_HASH_MODES.keys())),
        ToolOption("attack", "Attack mode (-a)", "choice",
                   default="0 (dictionary)", choices=["0 (dictionary)", "3 (brute)", "6 (hybrid)"]),
        ToolOption("wordlist", "Wordlist", "text", default="/usr/share/wordlists/rockyou.txt"),
        ToolOption("rules", "Rules file", "text", default=""),
        ToolOption("force", "Force (ignore warnings)", "bool", default=True),
    ]
    _CRACKED = re.compile(r"^([^:\s]+):(.+)$")

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("hashcat") is None:
            on_stderr("hashcat not installed (try: sudo pacman -S hashcat / sudo apt install hashcat)\n")
            return ToolResult(exit_code=127)
        mode = _HASH_MODES.get(str(args.get("mode") or "0 - MD5"), "0")
        attack = (args.get("attack") or "0 (dictionary)").split()[0]
        cmd = ["hashcat", "-m", mode, "-a", attack, target]
        if attack == "0" and args.get("wordlist"):
            cmd.append(str(args["wordlist"]))
        if args.get("rules"):
            cmd += ["-r", str(args["rules"])]
        if args.get("force"):
            cmd.append("--force")
        cmd += ["--quiet", "--status", "--status-timer=5"]
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []
        in_results = False

        def cb(line: str) -> None:
            nonlocal in_results
            on_stdout(line)
            s = line.strip()
            if not s:
                return
            m = self._CRACKED.match(s)
            if m and ":" in s and not s.startswith(("Session", "Status", "Time", "Progress", "Speed", "Recovered", "Candidates")):
                findings.append({
                    "title": f"cracked {m.group(1)[:32]} → {m.group(2)[:64]}",
                    "severity": "high",
                    "data": {"hash": m.group(1), "plain": m.group(2), "mode": mode},
                })

        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd, "mode": mode})


class JohnTool(Tool):
    name = "john"
    title = "John the Ripper — CPU password recovery"
    category = "password"
    description = "Crack password hashes on CPU. Target = path to hash file."
    requires_binary = "john"
    options = [
        ToolOption("format", "Hash format", "text", default="", help="e.g. raw-md5, sha512crypt, nt"),
        ToolOption("wordlist", "Wordlist", "text", default="/usr/share/wordlists/rockyou.txt"),
        ToolOption("rules", "Apply rules", "bool", default=True),
        ToolOption("incremental", "Incremental mode (no wordlist)", "bool", default=False),
    ]

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("john") is None:
            on_stderr("john not installed (try: sudo pacman -S john / sudo apt install john)\n")
            return ToolResult(exit_code=127)
        cmd = ["john"]
        if args.get("format"):
            cmd.append(f"--format={args['format']}")
        if args.get("incremental"):
            cmd.append("--incremental")
        else:
            cmd.append(f"--wordlist={args.get('wordlist') or '/usr/share/wordlists/rockyou.txt'}")
            if args.get("rules"):
                cmd.append("--rules")
        cmd.append(target)
        on_stdout(f"$ {' '.join(cmd)}\n")
        cracked: list[dict[str, Any]] = []

        def cb(line: str) -> None:
            on_stdout(line)
            s = line.strip()
            # john prints "password (user)" on cracked
            m = re.match(r"^(.+?)\s+\(([^)]+)\)$", s)
            if m and "loaded" not in s.lower() and "session" not in s.lower():
                cracked.append({
                    "title": f"cracked {m.group(2)} → {m.group(1)}",
                    "severity": "high",
                    "data": {"user": m.group(2), "plain": m.group(1)},
                })

        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        # Also call john --show to enumerate any already-cracked entries
        return ToolResult(exit_code=rc, findings=cracked, meta={"command": cmd})


class HydraTool(Tool):
    name = "hydra"
    title = "Hydra — network login brute force"
    category = "password"
    description = "Online brute-force login for many protocols. Target = host (service set in options)."
    requires_binary = "hydra"
    options = [
        ToolOption("service", "Service", "choice", default="ssh",
                   choices=["ssh", "ftp", "http-get", "http-post-form", "rdp", "smb", "mysql", "postgres", "vnc"]),
        ToolOption("port", "Port (0 = default)", "int", default=0),
        ToolOption("username", "Username", "text", default=""),
        ToolOption("userlist", "User list", "text", default=""),
        ToolOption("password", "Password", "text", default=""),
        ToolOption("passlist", "Password list", "text", default="/usr/share/wordlists/rockyou.txt"),
        ToolOption("threads", "Tasks (-t)", "int", default=4),
        ToolOption("stop_on_found", "Stop on first valid", "bool", default=True),
    ]
    _FOUND = re.compile(r"\[\d+\]\[\w+\]\s+host:\s*(\S+)\s+login:\s*(\S+)\s+password:\s*(\S+)")

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("hydra") is None:
            on_stderr("hydra not installed (try: sudo pacman -S hydra / sudo apt install hydra)\n")
            return ToolResult(exit_code=127)
        cmd = ["hydra"]
        if args.get("userlist"):
            cmd += ["-L", str(args["userlist"])]
        elif args.get("username"):
            cmd += ["-l", str(args["username"])]
        if args.get("passlist") and not args.get("password"):
            cmd += ["-P", str(args["passlist"])]
        elif args.get("password"):
            cmd += ["-p", str(args["password"])]
        cmd += ["-t", str(args.get("threads") or 4)]
        if args.get("stop_on_found"):
            cmd.append("-f")
        if args.get("port") and int(args["port"]) > 0:
            cmd += ["-s", str(args["port"])]
        cmd += [target, str(args.get("service") or "ssh")]
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []

        def cb(line: str) -> None:
            on_stdout(line)
            m = self._FOUND.search(line)
            if m:
                findings.append({
                    "title": f"valid creds {m.group(2)}:{m.group(3)} @ {m.group(1)}",
                    "severity": "critical", "host": m.group(1),
                    "service": str(args.get("service") or "ssh"),
                    "data": {"login": m.group(2), "password": m.group(3)},
                })

        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


registry.register(HashcatTool())
registry.register(JohnTool())
registry.register(HydraTool())
