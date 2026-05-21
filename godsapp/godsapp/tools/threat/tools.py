"""Threat Intelligence tools — Shodan, Censys, OTX, AbuseIPDB, MISP, ipinfo.

API keys are read from Settings → Threat Intelligence. ipinfo and OTX work
without keys (rate-limited); the others surface a clear error if their key
is unset. Author: Joseph Sierengowski.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from godsapp.core.settings import load_settings
from godsapp.tools.base import Tool, ToolOption, ToolResult
from godsapp.tools.registry import registry


def _threat_key(field: str) -> str:
    return (getattr(load_settings().threat, field, "") or "").strip()


def _sev_for_score(score: float) -> str:
    if score >= 90: return "critical"
    if score >= 60: return "high"
    if score >= 25: return "medium"
    if score >  0:  return "low"
    return "info"


# ────────────────────────────────────────────────────────────────────────────
class ShodanTool(Tool):
    name = "shodan"
    title = "Shodan — host intelligence"
    category = "threat"
    description = "Lookup an IPv4 host in Shodan. Set shodan_api_key in Settings → Threat Intel."
    requires_binary = None
    options = []

    async def run(self, target, args, *, on_stdout, on_stderr):
        key = _threat_key("shodan_api_key")
        if not key:
            on_stderr("Set shodan_api_key in Settings → Threat Intel.\n")
            return ToolResult(exit_code=2)
        url = f"https://api.shodan.io/shodan/host/{target}"
        on_stdout(f"GET {url}?key=***\n")
        try:
            async with httpx.AsyncClient(timeout=30.0) as cli:
                r = await cli.get(url, params={"key": key})
        except Exception as e:
            on_stderr(f"shodan error: {type(e).__name__}: {e}\n")
            return ToolResult(exit_code=1)
        if r.status_code != 200:
            on_stderr(f"HTTP {r.status_code}: {r.text[:200]}\n")
            return ToolResult(exit_code=1)
        data = r.json()
        findings: list[dict[str, Any]] = []
        for port in data.get("ports", []) or []:
            findings.append({"title": f"{target}:{port} open (shodan)",
                             "severity": "info", "host": target, "port": port})
        for cve in (data.get("vulns") or []):
            findings.append({"title": f"Shodan vuln: {cve} on {target}",
                             "severity": "high", "host": target,
                             "data": {"cve_id": cve}})
        findings.append({
            "title": f"{data.get('org','?')} · {data.get('country_name','?')} · {data.get('isp','?')} · AS{data.get('asn','?')}",
            "severity": "info", "host": target,
            "data": {"hostnames": data.get("hostnames"), "os": data.get("os"),
                     "last_update": data.get("last_update")},
        })
        on_stdout(json.dumps(data, indent=2, default=str)[:4000] + "\n")
        return ToolResult(exit_code=0, findings=findings)


class CensysTool(Tool):
    name = "censys"
    title = "Censys — host intelligence"
    category = "threat"
    description = "Lookup an IP in Censys. Requires censys_id + censys_secret in Settings."
    requires_binary = None
    options = []

    async def run(self, target, args, *, on_stdout, on_stderr):
        uid = _threat_key("censys_id"); secret = _threat_key("censys_secret")
        if not uid or not secret:
            on_stderr("Set censys_id + censys_secret in Settings → Threat Intel.\n")
            return ToolResult(exit_code=2)
        url = f"https://search.censys.io/api/v2/hosts/{target}"
        on_stdout(f"GET {url}\n")
        try:
            async with httpx.AsyncClient(timeout=30.0, auth=(uid, secret)) as cli:
                r = await cli.get(url)
        except Exception as e:
            on_stderr(f"censys error: {type(e).__name__}: {e}\n")
            return ToolResult(exit_code=1)
        if r.status_code != 200:
            on_stderr(f"HTTP {r.status_code}: {r.text[:200]}\n")
            return ToolResult(exit_code=1)
        data = (r.json() or {}).get("result", {})
        findings: list[dict[str, Any]] = []
        for svc in data.get("services", []) or []:
            port = svc.get("port"); proto = svc.get("transport_protocol", "tcp")
            sn = svc.get("service_name", "")
            findings.append({
                "title": f"{target}:{port}/{proto} {sn} (censys)",
                "severity": "info", "host": target, "port": port,
                "protocol": proto, "service": sn,
                "data": {k: v for k, v in svc.items() if k in
                         {"port","transport_protocol","service_name","banner","tls"}},
            })
        loc = data.get("location") or {}
        asn = (data.get("autonomous_system") or {}).get("asn", "?")
        findings.append({
            "title": f"{loc.get('country','?')} · {loc.get('city','?')} · AS{asn}",
            "severity": "info", "host": target,
            "data": {"location": loc, "as": data.get("autonomous_system")},
        })
        on_stdout(json.dumps(data, indent=2, default=str)[:4000] + "\n")
        return ToolResult(exit_code=0, findings=findings)


class OtxTool(Tool):
    name = "otx"
    title = "AlienVault OTX — pulses for indicator"
    category = "threat"
    description = ("Query OTX for pulses tied to an IP / domain / hash / URL. "
                   "API key is optional (anonymous calls work but are rate-limited).")
    requires_binary = None
    options = [ToolOption("indicator_type", "Indicator type", "choice",
                          default="IPv4",
                          choices=["IPv4", "IPv6", "domain", "hostname",
                                   "FileHash-MD5", "FileHash-SHA1",
                                   "FileHash-SHA256", "URL"])]

    async def run(self, target, args, *, on_stdout, on_stderr):
        key = _threat_key("otx_api_key")
        itype = str(args.get("indicator_type") or "IPv4")
        url = f"https://otx.alienvault.com/api/v1/indicators/{itype}/{target}/general"
        on_stdout(f"GET {url}\n")
        headers = {"X-OTX-API-KEY": key} if key else {}
        try:
            async with httpx.AsyncClient(timeout=30.0, headers=headers) as cli:
                r = await cli.get(url)
        except Exception as e:
            on_stderr(f"otx error: {type(e).__name__}: {e}\n")
            return ToolResult(exit_code=1)
        if r.status_code != 200:
            on_stderr(f"HTTP {r.status_code}: {r.text[:200]}\n")
            return ToolResult(exit_code=1)
        data = r.json()
        findings: list[dict[str, Any]] = []
        pi = data.get("pulse_info", {}) or {}
        for pulse in (pi.get("pulses") or [])[:15]:
            tags = pulse.get("tags") or []
            findings.append({
                "title": f"OTX: {pulse.get('name','?')[:120]} ({pulse.get('TLP','white')})",
                "severity": "medium", "host": target,
                "data": {"pulse_id": pulse.get("id"), "tags": tags,
                         "references": (pulse.get("references") or [])[:3],
                         "adversary": pulse.get("adversary"),
                         "malware_families": pulse.get("malware_families")},
            })
        if pi.get("count", 0) == 0:
            findings.append({"title": f"OTX: 0 pulses for {target}",
                             "severity": "info", "host": target})
        on_stdout(f"pulses: {pi.get('count', 0)}\n")
        return ToolResult(exit_code=0, findings=findings)


class AbuseIpDbTool(Tool):
    name = "abuseipdb"
    title = "AbuseIPDB — IP reputation"
    category = "threat"
    description = "Lookup an IP's abuse confidence score. Set abuseipdb_api_key in Settings."
    requires_binary = None
    options = [ToolOption("max_age_days", "Reports max age (days)", "int", default=90)]

    async def run(self, target, args, *, on_stdout, on_stderr):
        key = _threat_key("abuseipdb_api_key")
        if not key:
            on_stderr("Set abuseipdb_api_key in Settings → Threat Intel.\n")
            return ToolResult(exit_code=2)
        params = {"ipAddress": target,
                  "maxAgeInDays": int(args.get("max_age_days") or 90),
                  "verbose": ""}
        on_stdout("GET https://api.abuseipdb.com/api/v2/check\n")
        try:
            async with httpx.AsyncClient(timeout=30.0,
                                         headers={"Key": key, "Accept": "application/json"}) as cli:
                r = await cli.get("https://api.abuseipdb.com/api/v2/check", params=params)
        except Exception as e:
            on_stderr(f"abuseipdb error: {type(e).__name__}: {e}\n")
            return ToolResult(exit_code=1)
        if r.status_code != 200:
            on_stderr(f"HTTP {r.status_code}: {r.text[:200]}\n")
            return ToolResult(exit_code=1)
        data = (r.json() or {}).get("data", {})
        score = int(data.get("abuseConfidenceScore", 0) or 0)
        sev = _sev_for_score(score)
        findings = [{
            "title": (f"AbuseIPDB score {score}/100 — "
                      f"{data.get('countryCode','?')} · {data.get('isp','?')} "
                      f"· {data.get('totalReports',0)} reports"),
            "severity": sev, "host": target, "data": data,
        }]
        on_stdout(json.dumps(data, indent=2, default=str)[:2000] + "\n")
        return ToolResult(exit_code=0, findings=findings)


class IpInfoTool(Tool):
    name = "ipinfo"
    title = "ipinfo.io — geolocation (free, no key)"
    category = "threat"
    description = "Free IP geolocation + ASN lookup. No API key required."
    requires_binary = None
    options = []

    async def run(self, target, args, *, on_stdout, on_stderr):
        url = f"https://ipinfo.io/{target}/json"
        on_stdout(f"GET {url}\n")
        try:
            async with httpx.AsyncClient(timeout=30.0) as cli:
                r = await cli.get(url)
        except Exception as e:
            on_stderr(f"ipinfo error: {type(e).__name__}: {e}\n")
            return ToolResult(exit_code=1)
        if r.status_code != 200:
            on_stderr(f"HTTP {r.status_code}: {r.text[:200]}\n")
            return ToolResult(exit_code=1)
        data = r.json()
        findings = [{
            "title": (f"{data.get('city','?')}, {data.get('region','?')}, "
                      f"{data.get('country','?')} · {data.get('org','?')}"),
            "severity": "info", "host": target, "data": data,
        }]
        on_stdout(json.dumps(data, indent=2, default=str) + "\n")
        return ToolResult(exit_code=0, findings=findings)


class MispTool(Tool):
    name = "misp"
    title = "MISP — search events on your MISP server"
    category = "threat"
    description = "Search a MISP instance for events matching a value. Set misp_url + misp_key in Settings."
    requires_binary = None
    options = [
        ToolOption("limit", "Max events", "int", default=20),
    ]

    async def run(self, target, args, *, on_stdout, on_stderr):
        url = _threat_key("misp_url"); key = _threat_key("misp_key")
        if not url or not key:
            on_stderr("Set misp_url + misp_key in Settings → Threat Intel.\n")
            return ToolResult(exit_code=2)
        url = url.rstrip("/")
        endpoint = f"{url}/attributes/restSearch"
        on_stdout(f"POST {endpoint} value={target!r}\n")
        try:
            async with httpx.AsyncClient(
                timeout=30.0, verify=False,
                headers={"Authorization": key, "Accept": "application/json",
                         "Content-Type": "application/json"},
            ) as cli:
                r = await cli.post(endpoint,
                                   json={"value": target,
                                         "limit": int(args.get("limit") or 20)})
        except Exception as e:
            on_stderr(f"misp error: {type(e).__name__}: {e}\n")
            return ToolResult(exit_code=1)
        if r.status_code != 200:
            on_stderr(f"HTTP {r.status_code}: {r.text[:200]}\n")
            return ToolResult(exit_code=1)
        data = r.json()
        findings: list[dict[str, Any]] = []
        attrs = (data.get("response", {}) or {}).get("Attribute", []) or []
        for a in attrs:
            findings.append({
                "title": f"MISP {a.get('type')}: {a.get('value','')[:120]} (event {a.get('event_id')})",
                "severity": "medium", "host": target,
                "data": {"event_id": a.get("event_id"), "category": a.get("category"),
                         "type": a.get("type"), "to_ids": a.get("to_ids")},
            })
        on_stdout(f"matched {len(attrs)} attribute(s)\n")
        return ToolResult(exit_code=0, findings=findings)


registry.register(ShodanTool())
registry.register(CensysTool())
registry.register(OtxTool())
registry.register(AbuseIpDbTool())
registry.register(IpInfoTool())
registry.register(MispTool())
