"""Mobile tools — adb (Android Debug Bridge) and apktool (APK reverse engineering)."""
from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from godsapp.tools.base import Tool, ToolOption, ToolResult
from godsapp.tools.registry import registry


class AdbTool(Tool):
    name = "adb"
    title = "adb — Android device probe"
    category = "mobile"
    description = "Enumerate connected Android devices and probe them. Target = serial (or 'any')."
    requires_binary = "adb"
    options = [
        ToolOption("action", "Action", "choice", default="devices",
                   choices=["devices", "packages", "props", "logcat-tail", "running"]),
        ToolOption("filter", "Filter (regex)", "text", default=""),
        ToolOption("tail_lines", "logcat lines", "int", default=200),
    ]

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("adb") is None:
            on_stderr("adb not installed (try: sudo apt install android-tools-adb)\n")
            return ToolResult(exit_code=127)
        action = str(args.get("action") or "devices")
        base = ["adb"] if not target or target == "any" else ["adb", "-s", target]
        if action == "devices":
            cmd = ["adb", "devices", "-l"]
        elif action == "packages":
            cmd = base + ["shell", "pm", "list", "packages", "-f"]
        elif action == "props":
            cmd = base + ["shell", "getprop"]
        elif action == "logcat-tail":
            cmd = base + ["logcat", "-d", "-t", str(int(args.get("tail_lines") or 200))]
        elif action == "running":
            cmd = base + ["shell", "ps", "-A"]
        else:
            on_stderr(f"unknown action {action}\n")
            return ToolResult(exit_code=2)
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []
        pat = re.compile(str(args.get("filter") or "."))
        def cb(line: str) -> None:
            on_stdout(line)
            s = line.rstrip()
            if not s or not pat.search(s):
                return
            sev = "info"
            low = s.lower()
            if action == "packages" and any(k in low for k in ("debug", "test")):
                sev = "low"
            if action == "logcat-tail" and any(k in low for k in ("error", "fatal", "exception")):
                sev = "medium"
            findings.append({"title": s[:220], "severity": sev,
                             "data": {"action": action, "raw": s}})
        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


class ApktoolTool(Tool):
    name = "apktool"
    title = "apktool — APK decode / rebuild"
    category = "mobile"
    description = "Decode an APK to smali + resources, or rebuild a previously decoded tree."
    requires_binary = "apktool"
    options = [
        ToolOption("mode", "Mode", "choice", default="decode", choices=["decode", "build"]),
        ToolOption("output", "Output dir/APK (blank = auto)", "text", default=""),
        ToolOption("no_src", "Skip sources (-s)", "bool", default=False),
        ToolOption("no_res", "Skip resources (-r)", "bool", default=False),
    ]

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("apktool") is None:
            on_stderr("apktool not installed\n")
            return ToolResult(exit_code=127)
        mode = str(args.get("mode") or "decode")
        output = str(args.get("output") or "")
        if not output:
            if mode == "decode":
                output = tempfile.mkdtemp(prefix="godsapp-apktool-")
            else:
                output = str(Path(target).with_suffix(".rebuilt.apk"))
        cmd = ["apktool", "d" if mode == "decode" else "b", target, "-o", output, "-f"]
        if args.get("no_src"):
            cmd.append("-s")
        if args.get("no_res"):
            cmd.append("-r")
        on_stdout(f"$ {' '.join(cmd)}\n")
        rc = await self._run_subprocess(cmd, on_stdout=on_stdout, on_stderr=on_stderr)
        findings: list[dict[str, Any]] = []
        artifacts: list[str] = []
        if rc == 0:
            artifacts.append(output)
            findings.append({"title": f"{mode} → {output}", "severity": "info",
                             "data": {"mode": mode, "output": output}})
            if mode == "decode":
                manifest = Path(output) / "AndroidManifest.xml"
                if manifest.exists():
                    try:
                        text = manifest.read_text(errors="replace")
                        for perm in re.findall(r'android:name="(android\.permission\.[^"]+)"', text):
                            sev = "high" if any(k in perm for k in ("READ_SMS", "RECORD_AUDIO", "ACCESS_FINE_LOCATION", "READ_CONTACTS", "CAMERA")) else "low"
                            findings.append({"title": f"permission: {perm}", "severity": sev,
                                             "data": {"permission": perm}})
                    except Exception:
                        pass
        return ToolResult(exit_code=rc, findings=findings, artifacts=artifacts, meta={"command": cmd})


registry.register(AdbTool())
registry.register(ApktoolTool())
