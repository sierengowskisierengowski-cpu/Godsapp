"""Vulnerability scanning — Nuclei + CIRCL CVE search + Vulners search.

Author: Joseph Sierengowski.
"""
from __future__ import annotations

import json
import re
import shutil
from typing import Any

import httpx

from godsapp.tools.base import Tool, ToolOption, ToolResult
from godsapp.tools.registry import registry


class NucleiTool(Tool):
    name = "nuclei"
    title = "Nuclei — template-based vulnerability scanner"
    category = "vuln"
    description = "Fast, template-based scanner from ProjectDiscovery."
    requires_binary = "nuclei"
    options = [
        ToolOption("severity", "Severity filter", "text",
                   default="medium,high,critical"),
        ToolOption("templates", "Templates dir/file (-t)", "text", default=""),
        ToolOption("tags", "Tags (-tags)", "text", default=""),
        ToolOption("rate_limit", "Rate limit (-rl)", "int", default=150),
        ToolOption("concurrency", "Concurrency (-c)", "int", default=25),
        ToolOption("update_templates", "Update templates before scan", "bool", default=False),
    ]

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("nuclei") is None:
            on_stderr("nuclei not installed — `go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest`\n")
            return ToolResult(exit_code=127)
        if args.get("update_templates"):
            on_stdout("$ nuclei -ut\n")
            await self._run_subprocess(["nuclei", "-ut"], on_stdout=on_stdout, on_stderr=on_stderr)
        cmd = ["nuclei", "-u", target, "-jsonl", "-silent",
               "-severity", str(args.get("severity") or "medium,high,critical"),
               "-rl", str(args.get("rate_limit") or 150),
               "-c", str(args.get("concurrency") or 25)]
        if args.get("templates"):
            cmd += ["-t", str(args["templates"])]
        if args.get("tags"):
            cmd += ["-tags", str(args["tags"])]
        on_stdout(f"$ {' '.join(cmd)}\n")
        findings: list[dict[str, Any]] = []

        def cb(line: str) -> None:
            on_stdout(line)
            s = line.strip()
            if not s.startswith("{"):
                return
            try:
                row = json.loads(s)
            except Exception:
                return
            info = row.get("info", {})
            sev = info.get("severity", "info")
            template_id = row.get("template-id", "")
            matched_at = row.get("matched-at", target)
            findings.append({
                "title": f"{info.get('name', template_id)} → {matched_at}",
                "severity": sev,
                "host": target,
                "description": info.get("description", ""),
                "data": {
                    "template_id": template_id,
                    "matched_at": matched_at,
                    "tags": info.get("tags", []),
                    "reference": info.get("reference", []),
                    "classification": info.get("classification", {}),
                },
            })

        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


class CveSearchTool(Tool):
    name = "cve-search"
    title = "CVE Search — CIRCL public database"
    category = "vuln"
    description = ("Query CIRCL's free CVE database. Target = CVE-YYYY-NNNN for a single CVE, "
                   "or 'vendor:product' for a product search.")
    requires_binary = None
    options = [
        ToolOption("max_results", "Max results", "int", default=20),
    ]

    async def run(self, target, args, *, on_stdout, on_stderr):
        t = (target or "").strip()
        max_n = int(args.get("max_results") or 20)
        findings: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(timeout=30.0,
                                         headers={"User-Agent": "GodsApp/0.3 (Sierengowski)"}) as cli:
                if re.match(r"^CVE-\d{4}-\d{4,}$", t, re.I):
                    url = f"https://cve.circl.lu/api/cve/{t.upper()}"
                    on_stdout(f"GET {url}\n")
                    r = await cli.get(url)
                    if r.status_code != 200:
                        on_stderr(f"HTTP {r.status_code}\n"); return ToolResult(exit_code=1)
                    rows = [r.json()]
                else:
                    if ":" in t:
                        vendor, product = t.split(":", 1)
                    else:
                        vendor, product = "*", t
                    url = f"https://cve.circl.lu/api/search/{vendor}/{product}"
                    on_stdout(f"GET {url}\n")
                    r = await cli.get(url)
                    if r.status_code != 200:
                        on_stderr(f"HTTP {r.status_code}\n"); return ToolResult(exit_code=1)
                    data = r.json()
                    if isinstance(data, dict) and "results" in data:
                        rows = data["results"][:max_n]
                    elif isinstance(data, list):
                        rows = data[:max_n]
                    else:
                        rows = []
        except Exception as e:
            on_stderr(f"cve-search error: {type(e).__name__}: {e}\n")
            return ToolResult(exit_code=1)

        for row in rows:
            cve_id = row.get("id") or row.get("cveMetadata", {}).get("cveId", "?")
            summary = (row.get("summary") or "").strip()
            cvss_raw = row.get("cvss") or row.get("cvss3") or 0
            try:
                cvss = float(cvss_raw or 0)
            except (TypeError, ValueError):
                cvss = 0.0
            sev = ("critical" if cvss >= 9 else "high" if cvss >= 7
                   else "medium" if cvss >= 4 else "low" if cvss > 0 else "info")
            on_stdout(f"{cve_id} CVSS={cvss}  {summary[:140]}\n")
            findings.append({
                "title": f"{cve_id} (CVSS {cvss}) — {summary[:200]}",
                "severity": sev,
                "data": {
                    "cve_id": cve_id, "cvss": cvss, "summary": summary,
                    "references": (row.get("references") or [])[:5],
                    "vulnerable_configurations": (row.get("vulnerable_configuration") or [])[:5],
                },
            })
        return ToolResult(exit_code=0, findings=findings, meta={"query": t})


class VulnersSearchTool(Tool):
    name = "vulners-search"
    title = "Vulners — security database search (public API)"
    category = "vuln"
    description = "Search Vulners.com for an advisory by ID (e.g. CVE-2024-1234) or keyword."
    requires_binary = None
    options = [
        ToolOption("size", "Max results", "int", default=10),
    ]

    async def run(self, target, args, *, on_stdout, on_stderr):
        size = int(args.get("size") or 10)
        try:
            async with httpx.AsyncClient(timeout=30.0) as cli:
                url = "https://vulners.com/api/v3/search/lucene/"
                on_stdout(f"POST {url} query={target!r}\n")
                r = await cli.post(url, json={"query": target, "size": size})
        except Exception as e:
            on_stderr(f"vulners error: {type(e).__name__}: {e}\n")
            return ToolResult(exit_code=1)
        if r.status_code != 200:
            on_stderr(f"HTTP {r.status_code}: {r.text[:200]}\n")
            return ToolResult(exit_code=1)
        try:
            data = r.json()
        except Exception:
            on_stderr("vulners returned non-JSON response\n")
            return ToolResult(exit_code=1)
        findings: list[dict[str, Any]] = []
        for hit in (data.get("data", {}) or {}).get("search", []) or []:
            src = hit.get("_source", {})
            cvss = src.get("cvss", {}).get("score", 0) or 0
            try:
                cvss_f = float(cvss)
            except Exception:
                cvss_f = 0.0
            sev = ("critical" if cvss_f >= 9 else "high" if cvss_f >= 7
                   else "medium" if cvss_f >= 4 else "low" if cvss_f > 0 else "info")
            title = src.get("title", src.get("id", "?"))
            on_stdout(f"{src.get('id','?')} [{cvss_f}] {title[:120]}\n")
            findings.append({
                "title": f"{src.get('id','?')} CVSS={cvss_f} — {title[:200]}",
                "severity": sev,
                "data": {"vulners_id": src.get("id"), "type": src.get("type"),
                         "href": src.get("href"), "cvss": cvss_f},
            })
        return ToolResult(exit_code=0, findings=findings)


registry.register(NucleiTool())
registry.register(CveSearchTool())
registry.register(VulnersSearchTool())
