"""Additional network tools — `dig` DNS lookup and `arp-scan` LAN sweep.

Author: Joseph Sierengowski.
"""
from __future__ import annotations

import re
import shutil
from typing import Any

from godsapp.tools.base import Tool, ToolOption, ToolResult
from godsapp.tools.registry import registry


class DigTool(Tool):
    name = "dig"
    title = "dig — DNS resolver"
    category = "network"
    description = "Query DNS records for a name."
    requires_binary = "dig"
    options = [
        ToolOption("record_type", "Record type", "choice",
                   default="ANY",
                   choices=["A","AAAA","MX","NS","TXT","CNAME","SOA","SRV","CAA","ANY"]),
        ToolOption("resolver", "Resolver (@server)", "text", default=""),
        ToolOption("short", "Short output (+short)", "bool", default=False),
    ]
    _ANS = re.compile(r"^(\S+)\s+\d+\s+IN\s+(\S+)\s+(.+)$")

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("dig") is None:
            on_stderr("dig not installed (dnsutils / bind-utils)\n")
            return ToolResult(exit_code=127)
        cmd = ["dig"]
        if args.get("resolver"):
            cmd.append(f"@{args['resolver']}")
        cmd += [target, str(args.get("record_type") or "ANY"), "+nocomments", "+nostats"]
        if args.get("short"):
            cmd.append("+short")
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []

        def cb(line: str) -> None:
            on_stdout(line)
            s = line.rstrip()
            if not s or s.startswith(";") or s.startswith("#"):
                return
            m = self._ANS.match(s)
            if m:
                name, rtype, value = m.group(1), m.group(2), m.group(3)
                findings.append({"title": f"{name} {rtype} → {value[:200]}",
                                 "severity": "info", "host": target,
                                 "data": {"name": name, "rtype": rtype, "value": value}})

        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


class ArpScanTool(Tool):
    name = "arp-scan"
    title = "arp-scan — local network sweep"
    category = "network"
    description = "Discover hosts on the local L2 network via ARP. Target = interface (e.g. eth0) or CIDR."
    requires_binary = "arp-scan"
    options = [
        ToolOption("interface", "Interface (-I)", "text", default=""),
        ToolOption("localnet", "Use --localnet", "bool", default=True),
    ]
    _ROW = re.compile(r"^(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9a-fA-F:]{17})\s+(.+)$")

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("arp-scan") is None:
            on_stderr("arp-scan not installed\n")
            return ToolResult(exit_code=127)
        cmd = ["arp-scan", "--ignoredups", "--retry=1", "--timeout=400"]
        if args.get("interface"):
            cmd += ["-I", str(args["interface"])]
        if args.get("localnet") and "/" not in target:
            cmd.append("--localnet")
        else:
            cmd.append(target)
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []

        def cb(line: str) -> None:
            on_stdout(line)
            m = self._ROW.match(line.rstrip())
            if m:
                ip, mac, vendor = m.group(1), m.group(2), m.group(3)
                findings.append({
                    "title": f"{ip}  {mac}  {vendor[:120]}",
                    "severity": "info", "host": ip,
                    "data": {"mac": mac, "vendor": vendor},
                })

        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


registry.register(DigTool())
registry.register(ArpScanTool())
