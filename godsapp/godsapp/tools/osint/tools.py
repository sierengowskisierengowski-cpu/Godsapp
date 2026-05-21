"""OSINT tools — theHarvester, whois, sherlock."""
from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from godsapp.tools.base import Tool, ToolOption, ToolResult
from godsapp.tools.registry import registry


class TheHarvesterTool(Tool):
    name = "theharvester"
    title = "theHarvester — emails, subdomains, hosts"
    category = "osint"
    description = "Gather emails, names, subdomains, IPs from public sources."
    requires_binary = "theHarvester"
    options = [
        ToolOption("source", "Source(s)", "text", default="bing,duckduckgo,crtsh,hackertarget"),
        ToolOption("limit", "Limit", "int", default=200),
    ]
    _EMAIL = re.compile(r"^([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\s*$")
    _HOST = re.compile(r"^(\S+):(\d{1,3}(?:\.\d{1,3}){3})\s*$")

    async def run(self, target, args, *, on_stdout, on_stderr):
        bin_name = "theHarvester" if shutil.which("theHarvester") else ("theharvester" if shutil.which("theharvester") else None)
        if not bin_name:
            on_stderr("theHarvester not installed\n")
            return ToolResult(exit_code=127)
        cmd = [bin_name, "-d", target,
               "-b", str(args.get("source") or "bing,duckduckgo,crtsh"),
               "-l", str(int(args.get("limit") or 200))]
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []
        def cb(line: str) -> None:
            on_stdout(line)
            s = line.strip()
            m = self._EMAIL.match(s)
            if m:
                findings.append({"title": f"email: {m.group(1)}", "severity": "low",
                                 "host": target, "data": {"email": m.group(1)}})
                return
            m = self._HOST.match(s)
            if m:
                findings.append({"title": f"host: {m.group(1)} ({m.group(2)})", "severity": "info",
                                 "host": m.group(1), "data": {"ip": m.group(2)}})
        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


class WhoisTool(Tool):
    name = "whois"
    title = "whois — domain registration record"
    category = "osint"
    description = "Query WHOIS records for a domain or IP."
    requires_binary = "whois"
    options = []
    _FIELDS = {"registrar", "creation date", "registry expiry date", "updated date",
               "name server", "registrant", "admin email", "tech email", "org",
               "country", "netrange", "cidr"}

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("whois") is None:
            on_stderr("whois not installed\n")
            return ToolResult(exit_code=127)
        cmd = ["whois", target]
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []
        def cb(line: str) -> None:
            on_stdout(line)
            s = line.strip()
            if ":" not in s or s.startswith(("#", "%")):
                return
            key, _, val = s.partition(":")
            key_norm = key.strip().lower()
            val = val.strip()
            if not val:
                return
            if any(key_norm.startswith(k) for k in self._FIELDS):
                findings.append({"title": f"{key.strip()}: {val[:180]}", "severity": "info",
                                 "host": target, "data": {"key": key.strip(), "value": val}})
        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


class SherlockTool(Tool):
    name = "sherlock"
    title = "Sherlock — username across social networks"
    category = "osint"
    description = "Hunt down a username across hundreds of social networks."
    requires_binary = "sherlock"
    options = [
        ToolOption("timeout", "Per-site timeout (s)", "int", default=10),
        ToolOption("nsfw", "Include NSFW sites", "bool", default=False),
    ]
    _HIT = re.compile(r"^\[\+\]\s+(\S+):\s+(https?://\S+)")

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("sherlock") is None:
            on_stderr("sherlock not installed (pip install sherlock-project)\n")
            return ToolResult(exit_code=127)
        out_dir = Path(tempfile.mkdtemp(prefix="godsapp-sherlock-"))
        cmd = ["sherlock", "--print-found", "--no-color",
               "--timeout", str(int(args.get("timeout") or 10)),
               "--folderoutput", str(out_dir), target]
        if args.get("nsfw"):
            cmd.append("--nsfw")
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []
        def cb(line: str) -> None:
            on_stdout(line)
            m = self._HIT.match(line.rstrip())
            if m:
                findings.append({"title": f"{m.group(1)}: {m.group(2)}", "severity": "low",
                                 "data": {"site": m.group(1), "url": m.group(2)}})
        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings,
                          artifacts=[str(p) for p in out_dir.glob("*")],
                          meta={"command": cmd})


registry.register(TheHarvesterTool())
registry.register(WhoisTool())
registry.register(SherlockTool())
