"""Web Application tools — gobuster, nikto, whatweb. Real subprocess wrappers."""
from __future__ import annotations

import json
import re
import shutil
from typing import Any

from godsapp.tools.base import OutputCallback, Tool, ToolOption, ToolResult
from godsapp.tools.registry import registry


# ────────────────────────────────────────────────────────────────────────────
class GobusterDirTool(Tool):
    name = "gobuster-dir"
    title = "Gobuster — directory brute force"
    category = "web"
    description = "Brute-force web paths/directories using a wordlist."
    requires_binary = "gobuster"
    options = [
        ToolOption("wordlist", "Wordlist path", "text",
                   default="/usr/share/wordlists/dirb/common.txt"),
        ToolOption("extensions", "Extensions (comma)", "text", default=""),
        ToolOption("threads", "Threads", "int", default=20),
        ToolOption("status_codes", "Status codes", "text", default="200,204,301,302,307,401,403"),
    ]

    _LINE = re.compile(r"^(/\S+)\s+\(Status:\s*(\d+)\)\s+\[Size:\s*(\d+)")

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("gobuster") is None:
            on_stderr("gobuster not installed (try: sudo pacman -S gobuster / sudo apt install gobuster)\n")
            return ToolResult(exit_code=127)
        cmd = ["gobuster", "dir", "-u", target,
               "-w", str(args.get("wordlist") or "/usr/share/wordlists/dirb/common.txt"),
               "-t", str(args.get("threads") or 20),
               "-s", str(args.get("status_codes") or "200,204,301,302,307,401,403"),
               "--no-error", "--no-progress"]
        if args.get("extensions"):
            cmd += ["-x", str(args["extensions"])]
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []

        def line_collector(line: str) -> None:
            on_stdout(line)
            m = self._LINE.match(line.strip())
            if m:
                path, status, size = m.group(1), int(m.group(2)), int(m.group(3))
                sev = "info" if status in {301, 302, 307} else "low" if status == 200 else "medium" if status in {401, 403} else "info"
                findings.append({
                    "title": f"{path}  [{status}]",
                    "severity": sev,
                    "host": target,
                    "service": "http",
                    "description": f"size={size}",
                    "data": {"path": path, "status": status, "size": size},
                })

        rc = await self._run_subprocess(cmd, on_stdout=line_collector, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


# ────────────────────────────────────────────────────────────────────────────
class NiktoTool(Tool):
    name = "nikto"
    title = "Nikto — web server scanner"
    category = "web"
    description = "Scan web server for thousands of dangerous files, misconfigurations and vulnerabilities."
    requires_binary = "nikto"
    options = [
        ToolOption("port",       "Port", "int", default=80),
        ToolOption("ssl",        "SSL", "bool", default=False),
        ToolOption("tuning",     "Tuning (-Tuning)", "text", default="",
                   help="1=interesting files 2=misconfig 3=info disclosure 4=injection 5=remote retrieval 6=DoS 7=remote file 8=cmd exec 9=SQLi 0=auth b=software"),
    ]

    _LINE = re.compile(r"^\+\s+(.*)$")

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("nikto") is None:
            on_stderr("nikto not installed (try: sudo apt install nikto)\n")
            return ToolResult(exit_code=127)
        cmd = ["nikto", "-host", target, "-port", str(args.get("port") or 80), "-ask", "no", "-nointeractive"]
        if args.get("ssl"):
            cmd.append("-ssl")
        if args.get("tuning"):
            cmd += ["-Tuning", str(args["tuning"])]
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []

        def cb(line: str) -> None:
            on_stdout(line)
            m = self._LINE.match(line.rstrip())
            if not m:
                return
            text = m.group(1).strip()
            low = text.lower()
            sev = "info"
            if any(k in low for k in ("osvdb", "cve-", "xss", "sqli", "injection", "rce", "remote code")):
                sev = "high"
            elif any(k in low for k in ("retrieved", "uncommon header", "x-frame-options", "missing", "default")):
                sev = "low"
            findings.append({"title": text[:200], "severity": sev, "host": target, "service": "http"})

        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


# ────────────────────────────────────────────────────────────────────────────
class WhatWebTool(Tool):
    name = "whatweb"
    title = "WhatWeb — web tech fingerprint"
    category = "web"
    description = "Identify web technologies, CMS, frameworks, and JS libraries."
    requires_binary = "whatweb"
    options = [
        ToolOption("aggression", "Aggression level", "choice",
                   default="1", choices=["1", "3", "4"]),
    ]

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("whatweb") is None:
            on_stderr("whatweb not installed (try: sudo apt install whatweb)\n")
            return ToolResult(exit_code=127)
        cmd = ["whatweb", "-a", str(args.get("aggression") or "1"),
               "--log-json=-", "--colour=never", target]
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []
        buf: list[str] = []

        def cb(line: str) -> None:
            on_stdout(line)
            buf.append(line)

        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        try:
            payload = "".join(buf).strip()
            # whatweb --log-json writes a JSON array
            for entry in json.loads(payload):
                plugins = entry.get("plugins", {})
                for name, data in plugins.items():
                    ver = ",".join(data.get("version", [])) if isinstance(data, dict) else ""
                    title = f"{name}" + (f" {ver}" if ver else "")
                    findings.append({
                        "title": title, "severity": "info",
                        "host": entry.get("target", target),
                        "service": "http", "data": data if isinstance(data, dict) else {},
                    })
        except Exception:
            pass
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


registry.register(GobusterDirTool())
registry.register(NiktoTool())
registry.register(WhatWebTool())
