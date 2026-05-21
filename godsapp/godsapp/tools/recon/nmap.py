"""Nmap wrapper — real subprocess, XML parse, persisted findings."""
from __future__ import annotations

import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from godsapp.tools.base import OutputCallback, Tool, ToolOption, ToolResult
from godsapp.tools.registry import registry


class NmapTool(Tool):
    name = "nmap"
    title = "Nmap port + service scan"
    category = "recon"
    description = (
        "TCP/UDP port scanning, service/version detection, OS fingerprinting, "
        "and NSE script execution via the nmap binary."
    )
    requires_binary = "nmap"
    options = [
        ToolOption("profile", "Scan profile", "choice",
                   default="default", choices=["quick", "default", "thorough", "udp", "vuln"]),
        ToolOption("ports", "Ports (-p)", "text", default=""),
        ToolOption("service_detect", "Service/version detection (-sV)", "bool", default=True),
        ToolOption("os_detect", "OS detection (-O)", "bool", default=False),
        ToolOption("scripts", "NSE scripts (--script)", "text", default=""),
        ToolOption("timing", "Timing template (-T)", "choice",
                   default="4", choices=["0", "1", "2", "3", "4", "5"]),
    ]

    PROFILES = {
        "quick":    ["-T4", "-F"],
        "default":  ["-T4", "-sS", "--top-ports", "1000"],
        "thorough": ["-T4", "-sS", "-A", "-p-"],
        "udp":      ["-sU", "--top-ports", "200"],
        "vuln":     ["-sS", "--script", "vuln"],
    }

    async def run(self, target: str, args: dict[str, Any], *,
                  on_stdout: OutputCallback, on_stderr: OutputCallback) -> ToolResult:
        if shutil.which("nmap") is None:
            on_stderr("nmap not installed. Try: sudo pacman -S nmap (Arch) or sudo apt install nmap (Debian)\n")
            return ToolResult(exit_code=127)

        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as xf:
            xml_path = Path(xf.name)

        profile = args.get("profile", "default")
        cmd = ["nmap"]
        cmd += self.PROFILES.get(profile, self.PROFILES["default"])
        if args.get("service_detect"):
            cmd.append("-sV")
        if args.get("os_detect"):
            cmd.append("-O")
        if args.get("ports"):
            cmd += ["-p", str(args["ports"])]
        if args.get("scripts"):
            cmd += ["--script", str(args["scripts"])]
        if args.get("timing"):
            cmd.append(f"-T{args['timing']}")
        cmd += ["-oX", str(xml_path), target]

        on_stdout(f"$ {' '.join(cmd)}\n")
        exit_code = await self._run_subprocess(cmd, on_stdout=on_stdout, on_stderr=on_stderr)

        findings: list[dict[str, Any]] = []
        if xml_path.exists() and xml_path.stat().st_size > 0:
            try:
                findings = self._parse_xml(xml_path)
            except Exception as e:
                on_stderr(f"failed to parse nmap XML: {e}\n")
        try:
            xml_path.unlink(missing_ok=True)
        except Exception:
            pass

        return ToolResult(exit_code=exit_code, findings=findings,
                          meta={"profile": profile, "command": cmd})

    @staticmethod
    def _parse_xml(path: Path) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        root = ET.parse(path).getroot()
        for host in root.findall("host"):
            addr_el = host.find("address")
            if addr_el is None:
                continue
            host_addr = addr_el.get("addr", "")
            hostnames_el = host.find("hostnames")
            hostnames = (
                [h.get("name", "") for h in hostnames_el.findall("hostname")]
                if hostnames_el is not None else []
            )
            for port in host.findall("./ports/port"):
                state = port.find("state")
                if state is None or state.get("state") != "open":
                    continue
                portid = int(port.get("portid", "0") or 0)
                protocol = port.get("protocol", "tcp")
                svc = port.find("service")
                svc_name = svc.get("name", "") if svc is not None else ""
                svc_product = svc.get("product", "") if svc is not None else ""
                svc_version = svc.get("version", "") if svc is not None else ""
                title = f"{host_addr}:{portid}/{protocol}"
                if svc_name:
                    title += f" {svc_name}"
                if svc_product:
                    title += f" {svc_product} {svc_version}".rstrip()
                severity = "low" if svc_name in {"http", "https"} else "info"
                if svc_name in {"telnet", "ftp", "rsh", "rlogin"}:
                    severity = "high"
                findings.append({
                    "title": title.strip(),
                    "severity": severity,
                    "host": host_addr,
                    "port": portid,
                    "protocol": protocol,
                    "service": svc_name or None,
                    "description": svc_product or None,
                    "data": {"hostnames": hostnames,
                             "product": svc_product, "version": svc_version},
                })
        return findings


registry.register(NmapTool())
