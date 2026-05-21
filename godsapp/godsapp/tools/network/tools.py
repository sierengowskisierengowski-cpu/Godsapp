"""Network tools — masscan (fast port sweep), traceroute, ss (listening sockets)."""
from __future__ import annotations

import re
import shutil
from typing import Any

from godsapp.tools.base import Tool, ToolOption, ToolResult
from godsapp.tools.registry import registry


class MasscanTool(Tool):
    name = "masscan"
    title = "Masscan — internet-scale port scanner"
    category = "network"
    description = "Asynchronous TCP port scanner. Capable of scanning the entire internet in minutes."
    requires_binary = "masscan"
    options = [
        ToolOption("ports", "Ports", "text", default="1-1024"),
        ToolOption("rate",  "Packets/sec (--rate)", "int", default=1000),
        ToolOption("banners", "Grab banners", "bool", default=False),
    ]
    _LINE = re.compile(r"Discovered open port\s+(\d+)/(\w+)\s+on\s+(\S+)")

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("masscan") is None:
            on_stderr("masscan not installed (try: sudo pacman -S masscan / sudo apt install masscan)\n")
            return ToolResult(exit_code=127)
        cmd = ["masscan", target,
               "-p", str(args.get("ports") or "1-1024"),
               "--rate", str(args.get("rate") or 1000),
               "--wait", "0"]
        if args.get("banners"):
            cmd.append("--banners")
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []

        def cb(line: str) -> None:
            on_stdout(line)
            m = self._LINE.search(line)
            if m:
                port, proto, host = int(m.group(1)), m.group(2), m.group(3)
                findings.append({
                    "title": f"{host}:{port}/{proto} open",
                    "severity": "info", "host": host, "port": port, "protocol": proto,
                })

        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


class TracerouteTool(Tool):
    name = "traceroute"
    title = "Traceroute — path discovery"
    category = "network"
    description = "Trace the network path to a host using ICMP/UDP/TCP probes."
    requires_binary = "traceroute"
    options = [
        ToolOption("max_hops", "Max hops", "int", default=30),
        ToolOption("protocol", "Protocol", "choice", default="icmp", choices=["icmp", "udp", "tcp"]),
    ]
    _HOP = re.compile(r"^\s*(\d+)\s+(.+)$")

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("traceroute") is None:
            on_stderr("traceroute not installed (try: sudo apt install traceroute)\n")
            return ToolResult(exit_code=127)
        proto_flag = {"icmp": "-I", "udp": "-U", "tcp": "-T"}.get(args.get("protocol") or "icmp", "-I")
        cmd = ["traceroute", proto_flag, "-m", str(args.get("max_hops") or 30), target]
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []

        def cb(line: str) -> None:
            on_stdout(line)
            m = self._HOP.match(line)
            if m:
                hop, rest = int(m.group(1)), m.group(2).strip()
                if "*" not in rest:
                    findings.append({"title": f"hop {hop}: {rest[:200]}", "severity": "info",
                                     "host": target, "data": {"hop": hop, "raw": rest}})

        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


class SsListenTool(Tool):
    name = "ss-listen"
    title = "ss — local listening sockets"
    category = "network"
    description = "Enumerate listening TCP/UDP sockets and the processes that own them."
    requires_binary = "ss"
    options = [
        ToolOption("protocol", "Protocol", "choice", default="both", choices=["tcp", "udp", "both"]),
    ]
    _ROW = re.compile(r"^(\S+)\s+\S+\s+\S+\s+\S+\s+(\S+)\s+(\S+)(?:\s+(.*))?$")

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("ss") is None:
            on_stderr("ss not installed (part of iproute2)\n")
            return ToolResult(exit_code=127)
        flags = "-lntp" if (args.get("protocol") or "both") == "tcp" else \
                "-lnup" if args.get("protocol") == "udp" else "-lntup"
        cmd = ["ss", flags]
        on_stdout(f"$ {' '.join(cmd)}  (target {target} ignored — local probe)\n")
        findings: list[dict[str, Any]] = []
        first = True

        def cb(line: str) -> None:
            nonlocal first
            on_stdout(line)
            if first:
                first = False
                return
            m = self._ROW.match(line.rstrip())
            if m:
                proto, local, _peer, proc = m.group(1), m.group(2), m.group(3), m.group(4) or ""
                findings.append({
                    "title": f"{proto} {local}  {proc}".strip()[:200],
                    "severity": "info", "host": "localhost",
                    "protocol": proto, "data": {"local": local, "process": proc},
                })

        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


registry.register(MasscanTool())
registry.register(TracerouteTool())
registry.register(SsListenTool())
