"""Forensics tools — binwalk, exiftool, strings. Target = path to file."""
from __future__ import annotations

import re
import shutil
from typing import Any

from godsapp.tools.base import Tool, ToolOption, ToolResult
from godsapp.tools.registry import registry


class BinwalkTool(Tool):
    name = "binwalk"
    title = "Binwalk — firmware / embedded analyzer"
    category = "forensics"
    description = "Identify and optionally extract embedded files & signatures in a binary."
    requires_binary = "binwalk"
    options = [
        ToolOption("extract", "Extract (-e)", "bool", default=False),
        ToolOption("entropy", "Entropy analysis (-E)", "bool", default=False),
    ]
    _SIG = re.compile(r"^(\d+)\s+0x[0-9A-Fa-f]+\s+(.+)$")

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("binwalk") is None:
            on_stderr("binwalk not installed\n")
            return ToolResult(exit_code=127)
        cmd = ["binwalk"]
        if args.get("extract"):
            cmd.append("-e")
        if args.get("entropy"):
            cmd.append("-E")
        cmd.append(target)
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []
        def cb(line: str) -> None:
            on_stdout(line)
            m = self._SIG.match(line.rstrip())
            if m:
                desc = m.group(2)
                sev = "medium" if any(k in desc.lower() for k in ("private key", "certificate", "password")) else "info"
                findings.append({"title": f"@{m.group(1)}: {desc[:200]}",
                                 "severity": sev, "data": {"offset": int(m.group(1)), "raw": desc}})
        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


class ExiftoolTool(Tool):
    name = "exiftool"
    title = "ExifTool — metadata extractor"
    category = "forensics"
    description = "Read every EXIF / XMP / IPTC metadata tag from images, PDFs, documents."
    requires_binary = "exiftool"
    options = [
        ToolOption("group_names", "Show group names (-G)", "bool", default=True),
    ]
    _ROW = re.compile(r"^([^:]+?)\s*:\s*(.+)$")

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("exiftool") is None:
            on_stderr("exiftool not installed (try: sudo apt install libimage-exiftool-perl)\n")
            return ToolResult(exit_code=127)
        cmd = ["exiftool"]
        if args.get("group_names"):
            cmd.append("-G")
        cmd.append(target)
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []
        def cb(line: str) -> None:
            on_stdout(line)
            m = self._ROW.match(line.rstrip())
            if m:
                key, val = m.group(1).strip(), m.group(2).strip()
                low = (key + " " + val).lower()
                sev = "medium" if any(k in low for k in ("gps", "serial", "owner", "author", "creator", "software")) else "info"
                findings.append({"title": f"{key}: {val[:160]}", "severity": sev,
                                 "data": {"key": key, "value": val}})
        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


class StringsTool(Tool):
    name = "strings"
    title = "strings — printable strings extractor"
    category = "forensics"
    description = "Extract ASCII/UTF-8 strings of a minimum length from a binary."
    requires_binary = "strings"
    options = [
        ToolOption("min_length", "Min length (-n)", "int", default=8),
        ToolOption("filter", "Only keep matching (regex)", "text", default=""),
        ToolOption("max_findings", "Max findings stored", "int", default=200),
    ]

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("strings") is None:
            on_stderr("strings not installed (part of binutils)\n")
            return ToolResult(exit_code=127)
        cmd = ["strings", "-n", str(int(args.get("min_length") or 8)), target]
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []
        pat = re.compile(str(args.get("filter") or "."))
        cap = int(args.get("max_findings") or 200)
        def cb(line: str) -> None:
            on_stdout(line)
            s = line.rstrip()
            if not s or len(findings) >= cap:
                return
            if pat.search(s):
                low = s.lower()
                sev = "medium" if any(k in low for k in ("password", "secret", "api_key", "token", "begin rsa")) else "info"
                findings.append({"title": s[:200], "severity": sev})
        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


registry.register(BinwalkTool())
registry.register(ExiftoolTool())
registry.register(StringsTool())
