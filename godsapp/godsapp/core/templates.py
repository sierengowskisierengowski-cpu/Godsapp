"""Workspace templates — pre-configured engagement starters.

Each template defines: id, title, description, default_target, default_tags,
pre-populated note, recommended tool keys, and an optional default report format.

Templates are read-only built-ins for now; the Settings → Templates page will
let users save custom templates in v0.4.1.

Author: Joseph Sierengowski.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorkspaceTemplate:
    id: str
    title: str
    description: str
    default_target: str = ""
    default_tags: tuple[str, ...] = ()
    welcome_note: str = ""
    recommended_tools: tuple[str, ...] = ()
    default_report_format: str = "markdown"


TEMPLATES: list[WorkspaceTemplate] = [
    WorkspaceTemplate(
        id="blank",
        title="Blank Workspace",
        description="Start fresh — nothing pre-filled.",
    ),
    WorkspaceTemplate(
        id="bug-bounty",
        title="Bug Bounty — Web Target",
        description="Wildcard domain, web recon stack, markdown reports.",
        default_target="*.example.com",
        default_tags=("bug-bounty", "web"),
        welcome_note=(
            "# Bug Bounty Engagement\n\n"
            "## Scope\n- Primary: *.example.com\n- Out of scope: \n\n"
            "## Reward Tiers\n- Critical: $\n- High: $\n\n"
            "## Notes\n- "
        ),
        recommended_tools=("subdomain-brute", "gobuster", "nuclei", "sqlmap", "nikto"),
        default_report_format="markdown",
    ),
    WorkspaceTemplate(
        id="ext-pentest",
        title="External Penetration Test",
        description="IPs and CIDRs, full port scan, executive report.",
        default_target="203.0.113.0/24",
        default_tags=("pentest", "external"),
        welcome_note=(
            "# External Penetration Test\n\n"
            "## Rules of Engagement\n- Start: \n- End: \n- Authorised tester: \n- "
            "Client contact: \n\n## Scope\n"
        ),
        recommended_tools=("nmap", "masscan", "nikto", "sqlmap"),
        default_report_format="pdf",
    ),
    WorkspaceTemplate(
        id="int-pentest",
        title="Internal Penetration Test",
        description="Domain recon, internal network, credential findings.",
        default_target="10.0.0.0/16",
        default_tags=("pentest", "internal", "ad"),
        welcome_note=(
            "# Internal Penetration Test\n\n## Domain\n- Domain name: \n- DC: \n\n"
            "## Credentials Provided\n- "
        ),
        recommended_tools=("nmap", "masscan", "hydra", "hashcat", "tshark"),
        default_report_format="docx",
    ),
    WorkspaceTemplate(
        id="red-team",
        title="Red Team Engagement",
        description="Stealth-first, campaign tracking, deconfliction.",
        default_target="",
        default_tags=("red-team", "stealth"),
        welcome_note=(
            "# Red Team Engagement\n\n## Operation Name\n\n## ROE Summary\n\n"
            "## Deconfliction Contact\n\n## Detection Goals\n"
        ),
        recommended_tools=("nmap", "subdomain-brute", "theharvester"),
        default_report_format="markdown",
    ),
    WorkspaceTemplate(
        id="threat-hunt",
        title="Threat Hunt",
        description="Intel-only, no active exploitation enabled.",
        default_target="",
        default_tags=("threat-intel", "hunt"),
        welcome_note=(
            "# Threat Hunt\n\n## Hypothesis\n\n## IOCs to Investigate\n\n"
            "## Data Sources\n- "
        ),
        recommended_tools=("theharvester", "amass", "dnsrecon"),
        default_report_format="markdown",
    ),
    WorkspaceTemplate(
        id="forensics",
        title="Forensics Investigation",
        description="Read-only by default, chain of custody mandatory.",
        default_target="",
        default_tags=("forensics", "ir"),
        welcome_note=(
            "# Forensics Investigation\n\n## Case ID\n\n## Custodian\n\n"
            "## Acquisition Method\n\n## Timeline\n- "
        ),
        recommended_tools=("tshark",),
        default_report_format="pdf",
    ),
    WorkspaceTemplate(
        id="ctf",
        title="CTF (Capture the Flag)",
        description="All tools enabled, fast-mode, points tracker.",
        default_target="127.0.0.1",
        default_tags=("ctf", "learning"),
        welcome_note=(
            "# CTF\n\n## Event\n\n## Team\n\n## Flag Tracker\n- [ ] \n\n"
            "## Points\n- Current: 0\n- Target: \n"
        ),
        recommended_tools=("nmap", "gobuster", "hydra", "sqlmap", "hashcat"),
        default_report_format="markdown",
    ),
    WorkspaceTemplate(
        id="compliance",
        title="Compliance Audit",
        description="PCI / HIPAA / SOC 2 / ISO 27001 framework reports.",
        default_target="",
        default_tags=("compliance", "audit"),
        welcome_note=(
            "# Compliance Audit\n\n## Framework\n- [ ] PCI DSS\n- [ ] HIPAA\n"
            "- [ ] SOC 2\n- [ ] ISO 27001\n\n## Scope\n\n## Controls in Scope\n- "
        ),
        recommended_tools=("nmap", "nikto"),
        default_report_format="docx",
    ),
    WorkspaceTemplate(
        id="home-lab",
        title="Home Lab / Personal Research",
        description="Relaxed prompts, easy defaults, experimentation friendly.",
        default_target="192.168.0.0/24",
        default_tags=("homelab", "research"),
        welcome_note=(
            "# Home Lab\n\n## What I'm exploring\n\n## Targets\n- 192.168.0.0/24\n\n"
            "## Lessons learned\n- "
        ),
        recommended_tools=("nmap", "gobuster", "sqlmap"),
        default_report_format="markdown",
    ),
]


def get_template(template_id: str) -> WorkspaceTemplate | None:
    for t in TEMPLATES:
        if t.id == template_id:
            return t
    return None
