"""Wireless tools — iwlist scan and airodump-ng capture."""
from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from godsapp.tools.base import Tool, ToolOption, ToolResult
from godsapp.tools.registry import registry


class IwlistScanTool(Tool):
    name = "iwlist-scan"
    title = "iwlist — wireless network scan"
    category = "wireless"
    description = "Passive scan for nearby Wi-Fi access points. Target = interface (e.g. wlan0)."
    requires_binary = "iwlist"
    options = []
    _CELL = re.compile(r"Cell\s+\d+ - Address:\s+([0-9A-Fa-f:]{17})")
    _ESSID = re.compile(r'ESSID:"([^"]*)"')
    _SIGNAL = re.compile(r"Signal level=(-?\d+)\s*dBm")
    _ENC = re.compile(r"Encryption key:(on|off)")
    _CHAN = re.compile(r"Channel:?\s*(\d+)")

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("iwlist") is None:
            on_stderr("iwlist not installed (provided by wireless-tools)\n")
            return ToolResult(exit_code=127)
        iface = target or "wlan0"
        cmd = ["iwlist", iface, "scan"]
        on_stdout(f"$ {' '.join(cmd)}\n")
        buf: list[str] = []
        def cb(line: str) -> None:
            buf.append(line)
            on_stdout(line)
        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        text = "".join(buf)
        findings: list[dict[str, Any]] = []
        for block in re.split(r"(?=Cell\s+\d+ - Address:)", text):
            m_addr = self._CELL.search(block)
            if not m_addr:
                continue
            bssid = m_addr.group(1)
            essid = (self._ESSID.search(block) or [None, ""])[1] if self._ESSID.search(block) else ""
            essid = self._ESSID.search(block).group(1) if self._ESSID.search(block) else ""
            sig = self._SIGNAL.search(block)
            enc = self._ENC.search(block)
            ch = self._CHAN.search(block)
            open_net = bool(enc and enc.group(1) == "off")
            sev = "medium" if open_net else "info"
            findings.append({
                "title": f"{essid or '(hidden)'} [{bssid}] ch={ch.group(1) if ch else '?'} sig={sig.group(1) if sig else '?'}dBm {'OPEN' if open_net else 'encrypted'}",
                "severity": sev, "host": bssid,
                "data": {"bssid": bssid, "essid": essid, "channel": int(ch.group(1)) if ch else None,
                         "signal_dbm": int(sig.group(1)) if sig else None, "open": open_net},
            })
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd, "iface": iface})


class AirodumpTool(Tool):
    name = "airodump-ng"
    title = "airodump-ng — 802.11 capture"
    category = "wireless"
    description = "Capture 802.11 frames from a monitor-mode interface. Target = monitor iface (e.g. wlan0mon)."
    requires_binary = "airodump-ng"
    options = [
        ToolOption("duration", "Seconds to capture (timeout)", "int", default=15),
        ToolOption("channel", "Channel (0 = hop)", "int", default=0),
        ToolOption("bssid", "Target BSSID (optional)", "text", default=""),
    ]

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("airodump-ng") is None or shutil.which("timeout") is None:
            on_stderr("airodump-ng / timeout missing (provided by aircrack-ng + coreutils)\n")
            return ToolResult(exit_code=127)
        outdir = Path(tempfile.mkdtemp(prefix="godsapp-airodump-"))
        prefix = str(outdir / "cap")
        cmd = ["timeout", str(int(args.get("duration") or 15)),
               "airodump-ng", target or "wlan0mon",
               "-w", prefix, "--output-format", "csv"]
        if args.get("channel") and int(args["channel"]) > 0:
            cmd += ["-c", str(int(args["channel"]))]
        if args.get("bssid"):
            cmd += ["--bssid", str(args["bssid"])]
        on_stdout(f"$ {' '.join(cmd)}\n")
        rc = await self._run_subprocess(cmd, on_stdout=on_stdout, on_stderr=on_stderr)
        findings: list[dict[str, Any]] = []
        for csv_path in outdir.glob("cap-*.csv"):
            try:
                text = csv_path.read_text(errors="replace")
                # airodump csv has two sections separated by blank line; first = APs
                ap_block = text.split("\n\nStation MAC", 1)[0]
                for line in ap_block.splitlines()[2:]:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) < 14 or not parts[0]:
                        continue
                    bssid, ch, enc, essid = parts[0], parts[3], parts[5], parts[13]
                    findings.append({
                        "title": f"{essid or '(hidden)'} [{bssid}] ch={ch} {enc}",
                        "severity": "info", "host": bssid,
                        "data": {"bssid": bssid, "channel": ch, "encryption": enc, "essid": essid},
                    })
            except Exception as e:
                on_stderr(f"parse {csv_path}: {e}\n")
        return ToolResult(exit_code=rc, findings=findings,
                          artifacts=[str(p) for p in outdir.glob("cap-*")],
                          meta={"command": cmd, "capture_dir": str(outdir)})


registry.register(IwlistScanTool())
registry.register(AirodumpTool())
