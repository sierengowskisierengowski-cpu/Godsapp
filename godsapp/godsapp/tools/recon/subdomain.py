"""Built-in subdomain enumeration using DNS resolution (no external binary)."""
from __future__ import annotations

import asyncio
from typing import Any

import dns.resolver

from godsapp.tools.base import OutputCallback, Tool, ToolOption, ToolResult
from godsapp.tools.registry import registry

DEFAULT_WORDLIST = [
    "www", "mail", "ftp", "smtp", "pop", "imap", "webmail", "ns1", "ns2",
    "dns", "admin", "test", "dev", "staging", "stage", "api", "vpn", "git",
    "shop", "store", "blog", "forum", "wiki", "cdn", "static", "media",
    "files", "download", "uploads", "assets", "img", "images", "video",
    "secure", "ssl", "portal", "panel", "cpanel", "whm", "remote", "ssh",
    "intranet", "extranet", "corp", "internal", "auth", "sso", "id",
    "support", "help", "docs", "kb", "status", "monitor", "metrics", "logs",
    "demo", "beta", "alpha", "preview", "old", "new", "m", "mobile", "app",
    "dashboard", "console", "manage", "control",
]


class SubdomainBrute(Tool):
    name = "subdomain-brute"
    title = "Subdomain enumeration (DNS bruteforce)"
    category = "recon"
    description = "Resolve common subdomain candidates with concurrent DNS lookups."
    options = [
        ToolOption("concurrency", "Concurrent lookups", "int", default=20),
        ToolOption("wordlist_path", "Custom wordlist file (one per line, empty = built-in)",
                   "text", default=""),
        ToolOption("record", "DNS record", "choice", default="A",
                   choices=["A", "AAAA", "CNAME"]),
    ]

    async def run(self, target: str, args: dict[str, Any], *,
                  on_stdout: OutputCallback, on_stderr: OutputCallback) -> ToolResult:
        words = self._load_wordlist(args.get("wordlist_path") or "")
        record = (args.get("record") or "A").upper()
        concurrency = max(1, int(args.get("concurrency") or 20))

        on_stdout(f"# {len(words)} candidates against {target} ({record})\n")
        sem = asyncio.Semaphore(concurrency)
        findings: list[dict[str, Any]] = []

        resolver = dns.resolver.Resolver()
        resolver.lifetime = 3.0
        resolver.timeout = 2.0

        async def lookup(word: str) -> None:
            host = f"{word}.{target}"
            async with sem:
                try:
                    answers = await asyncio.to_thread(resolver.resolve, host, record)
                except Exception:
                    return
                addrs = [r.to_text() for r in answers]
                if not addrs:
                    return
                line = f"{host} -> {', '.join(addrs)}\n"
                on_stdout(line)
                findings.append({
                    "title": f"Subdomain {host}",
                    "severity": "info",
                    "host": host,
                    "port": None,
                    "protocol": None,
                    "service": None,
                    "description": ", ".join(addrs),
                    "data": {"record": record, "addresses": addrs},
                })

        await asyncio.gather(*(lookup(w) for w in words))
        on_stdout(f"# done — {len(findings)} subdomains discovered\n")
        return ToolResult(exit_code=0, findings=findings,
                          meta={"resolved": len(findings), "tried": len(words)})

    @staticmethod
    def _load_wordlist(path: str) -> list[str]:
        if not path:
            return DEFAULT_WORDLIST
        try:
            with open(path, "r", encoding="utf-8") as f:
                return [w.strip() for w in f if w.strip() and not w.startswith("#")]
        except OSError:
            return DEFAULT_WORDLIST


registry.register(SubdomainBrute())
