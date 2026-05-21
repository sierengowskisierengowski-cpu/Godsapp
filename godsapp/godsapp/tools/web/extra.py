"""Additional web tools — FFUF, SQLMap, WPScan, JWT analyzer, SSL/TLS analyzer.

Author: Joseph Sierengowski.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import ssl
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from godsapp.tools.base import Tool, ToolOption, ToolResult
from godsapp.tools.registry import registry


class FfufTool(Tool):
    name = "ffuf"
    title = "FFUF — fast web fuzzer"
    category = "web"
    description = "Web fuzzer. Use `FUZZ` as the marker in the target URL."
    requires_binary = "ffuf"
    options = [
        ToolOption("wordlist", "Wordlist (-w)", "text",
                   default="/usr/share/wordlists/dirb/common.txt"),
        ToolOption("filter_codes", "Filter status codes (-fc)", "text", default="404"),
        ToolOption("match_codes", "Match status codes (-mc)", "text",
                   default="200,204,301,302,307,401,403"),
        ToolOption("threads", "Threads (-t)", "int", default=40),
    ]

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("ffuf") is None:
            on_stderr("ffuf not installed\n")
            return ToolResult(exit_code=127)
        if "FUZZ" not in target:
            on_stderr("target must contain the FUZZ marker, e.g. https://x.com/FUZZ\n")
            return ToolResult(exit_code=2)
        cmd = ["ffuf", "-u", target,
               "-w", str(args.get("wordlist") or "/usr/share/wordlists/dirb/common.txt"),
               "-mc", str(args.get("match_codes") or "200,204,301,302,307,401,403"),
               "-fc", str(args.get("filter_codes") or "404"),
               "-t", str(args.get("threads") or 40),
               "-of", "json", "-o", "-", "-s"]
        on_stdout(f"$ {' '.join(cmd)}\n")
        buf: list[str] = []

        def cb(line: str) -> None:
            buf.append(line); on_stdout(line)

        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        findings: list[dict[str, Any]] = []
        try:
            data = json.loads("".join(buf) or "{}")
            for res in data.get("results", []):
                url = res.get("url", "")
                status = res.get("status", 0)
                size = res.get("length", 0)
                sev = ("medium" if status in (401, 403) else
                       "low" if status == 200 else "info")
                findings.append({
                    "title": f"{url}  [{status}, {size}B]",
                    "severity": sev, "host": urlparse(url).hostname,
                    "service": "http", "data": res,
                })
        except Exception as e:
            on_stderr(f"ffuf json parse failed: {type(e).__name__}: {e}\n")
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


class SqlmapTool(Tool):
    name = "sqlmap"
    title = "SQLMap — SQL injection detector"
    category = "web"
    description = "Automatic SQL injection / DB takeover. Use with --batch."
    requires_binary = "sqlmap"
    options = [
        ToolOption("level", "Level (1-5)", "int", default=1),
        ToolOption("risk", "Risk (1-3)", "int", default=1),
        ToolOption("technique", "Techniques (BEUSTQ)", "text", default="BEUSTQ"),
        ToolOption("data", "POST data", "text", default=""),
        ToolOption("cookie", "Cookie header", "text", default=""),
    ]

    _VULN = re.compile(r"Parameter:\s+(\S+)\s+\((\w+)\)")

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("sqlmap") is None:
            on_stderr("sqlmap not installed\n")
            return ToolResult(exit_code=127)
        cmd = ["sqlmap", "-u", target, "--batch", "--disable-coloring",
               "--level", str(args.get("level") or 1),
               "--risk", str(args.get("risk") or 1),
               "--technique", str(args.get("technique") or "BEUSTQ")]
        if args.get("data"):
            cmd += ["--data", str(args["data"])]
        if args.get("cookie"):
            cmd += ["--cookie", str(args["cookie"])]
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []

        def cb(line: str) -> None:
            on_stdout(line)
            m = self._VULN.search(line)
            if m:
                findings.append({
                    "title": f"SQLi: parameter {m.group(1)} ({m.group(2)}) on {target}",
                    "severity": "critical", "host": target, "service": "http",
                    "data": {"parameter": m.group(1), "method": m.group(2)},
                })

        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


class WpscanTool(Tool):
    name = "wpscan"
    title = "WPScan — WordPress vulnerability scanner"
    category = "web"
    description = "Enumerate WordPress vulns, plugins, users, themes."
    requires_binary = "wpscan"
    options = [
        ToolOption("enumerate", "Enumerate (--enumerate)", "text",
                   default="vp,vt,u,dbe"),
        ToolOption("api_token", "WPScan API token (optional)", "password", default=""),
    ]

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("wpscan") is None:
            on_stderr("wpscan not installed\n")
            return ToolResult(exit_code=127)
        cmd = ["wpscan", "--url", target, "--no-banner", "--no-update",
               "--enumerate", str(args.get("enumerate") or "vp,vt,u"),
               "--format", "json"]
        if args.get("api_token"):
            cmd += ["--api-token", str(args["api_token"])]
        on_stdout(f"$ {' '.join(c if c != args.get('api_token') else '***' for c in cmd)}\n")
        buf: list[str] = []
        def cb(line: str) -> None:
            buf.append(line); on_stdout(line)
        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        findings: list[dict[str, Any]] = []
        try:
            data = json.loads("".join(buf) or "{}")
            # Vulnerabilities under various sections
            for plugin_name, plugin in (data.get("plugins") or {}).items():
                for v in plugin.get("vulnerabilities", []) or []:
                    findings.append({
                        "title": f"plugin {plugin_name}: {v.get('title','?')}",
                        "severity": "high", "host": target, "service": "http",
                        "data": {"plugin": plugin_name, "fixed_in": v.get("fixed_in"),
                                 "references": v.get("references")},
                    })
            for theme_name, theme in (data.get("themes") or {}).items():
                for v in theme.get("vulnerabilities", []) or []:
                    findings.append({
                        "title": f"theme {theme_name}: {v.get('title','?')}",
                        "severity": "high", "host": target, "service": "http",
                        "data": {"theme": theme_name, "references": v.get("references")},
                    })
            for u in (data.get("users") or {}):
                findings.append({"title": f"WP user enumerated: {u}",
                                 "severity": "low", "host": target, "service": "http"})
        except Exception as e:
            on_stderr(f"wpscan json parse failed: {type(e).__name__}: {e}\n")
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


class JwtAnalyzerTool(Tool):
    name = "jwt-analyzer"
    title = "JWT analyzer — decode + weakness heuristics"
    category = "web"
    description = "Decode a JWT and flag common weaknesses (alg=none, weak HS256, missing exp). Target = the token."
    requires_binary = None
    options = []

    async def run(self, target, args, *, on_stdout, on_stderr):
        token = (target or "").strip().strip('"').strip("'")
        if token.count(".") < 2:
            on_stderr("expected three base64url-encoded segments separated by '.'\n")
            return ToolResult(exit_code=2)
        parts = token.split(".")
        try:
            header = json.loads(_b64url(parts[0]).decode())
            payload = json.loads(_b64url(parts[1]).decode())
        except Exception as e:
            on_stderr(f"decode failed: {e}\n")
            return ToolResult(exit_code=1)
        on_stdout("HEADER:  " + json.dumps(header, indent=2) + "\n")
        on_stdout("PAYLOAD: " + json.dumps(payload, indent=2, default=str) + "\n")
        findings: list[dict[str, Any]] = []
        alg = (header.get("alg") or "").lower()
        if alg in ("none", ""):
            findings.append({"title": "JWT alg=none — signature bypass possible",
                             "severity": "critical", "data": {"header": header}})
        elif alg == "hs256":
            findings.append({"title": "HS256 in use — brute-forceable with a weak shared secret",
                             "severity": "medium", "data": {"header": header}})
        if "exp" not in payload:
            findings.append({"title": "JWT has no `exp` claim — tokens never expire",
                             "severity": "medium", "data": {"payload_keys": list(payload.keys())}})
        elif isinstance(payload.get("exp"), (int, float)):
            try:
                exp = datetime.utcfromtimestamp(payload["exp"])
                if exp < datetime.utcnow():
                    findings.append({"title": f"JWT expired ({exp.isoformat()}Z)",
                                     "severity": "info", "data": {"exp": payload["exp"]}})
            except Exception:
                pass
        if "kid" in header:
            findings.append({"title": f"JWT uses kid={header['kid']!r} — review server-side resolution for path traversal",
                             "severity": "low", "data": {"kid": header["kid"]}})
        return ToolResult(exit_code=0, findings=findings,
                          meta={"header": header, "payload": payload})


def _b64url(s: str) -> bytes:
    pad = 4 - len(s) % 4
    if pad and pad < 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s.encode())


class SslTlsAnalyzerTool(Tool):
    name = "ssl-tls"
    title = "SSL / TLS analyzer"
    category = "web"
    description = ("Inspect the certificate + negotiated TLS of a host. "
                   "Target = host[:port] (port defaults to 443).")
    requires_binary = None
    options = []

    async def run(self, target, args, *, on_stdout, on_stderr):
        host = target
        port = 443
        if ":" in target and not target.startswith("["):
            host, p = target.rsplit(":", 1)
            try:
                port = int(p)
            except ValueError:
                port = 443
        on_stdout(f"Probing TLS on {host}:{port}\n")
        import socket
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            with socket.create_connection((host, port), timeout=15) as raw:
                with ctx.wrap_socket(raw, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
        except Exception as e:
            on_stderr(f"connect failed: {type(e).__name__}: {e}\n")
            return ToolResult(exit_code=1)
        on_stdout(f"version={version}  cipher={cipher}\n")
        on_stdout(json.dumps(cert, indent=2, default=str) + "\n")
        findings: list[dict[str, Any]] = []
        if version in ("TLSv1", "TLSv1.1", "SSLv3", "SSLv2"):
            findings.append({"title": f"weak TLS version: {version}",
                             "severity": "high", "host": host, "port": port,
                             "data": {"version": version}})
        # Cert expiry
        not_after = cert.get("notAfter")
        if not_after:
            try:
                expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                days = (expiry - datetime.utcnow()).days
                if days < 0:
                    findings.append({"title": f"certificate expired {abs(days)} days ago",
                                     "severity": "critical", "host": host, "port": port,
                                     "data": {"not_after": not_after}})
                elif days < 14:
                    findings.append({"title": f"certificate expires in {days} days",
                                     "severity": "medium", "host": host, "port": port,
                                     "data": {"not_after": not_after}})
                else:
                    findings.append({"title": f"certificate valid for {days} days",
                                     "severity": "info", "host": host, "port": port,
                                     "data": {"not_after": not_after}})
            except Exception:
                pass
        # Subject + issuer
        subj = dict(x[0] for x in cert.get("subject", [])) if cert.get("subject") else {}
        issuer = dict(x[0] for x in cert.get("issuer", [])) if cert.get("issuer") else {}
        findings.append({
            "title": f"CN={subj.get('commonName','?')} issued by {issuer.get('commonName','?')}",
            "severity": "info", "host": host, "port": port,
            "data": {"subject": subj, "issuer": issuer, "cipher": cipher, "version": version},
        })
        return ToolResult(exit_code=0, findings=findings)


registry.register(FfufTool())
registry.register(SqlmapTool())
registry.register(WpscanTool())
registry.register(JwtAnalyzerTool())
registry.register(SslTlsAnalyzerTool())
