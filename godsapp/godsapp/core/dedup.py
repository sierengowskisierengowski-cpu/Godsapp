"""Findings deduplication helpers.

Given a candidate finding (dict or ORM row), score how similar it is to each
existing finding in the same workspace. Callers decide what to do based on the
configured threshold.

Author: Joseph Sierengowski.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select

from godsapp.db import Finding, Scan, get_session

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _tokens(s: str | None) -> set[str]:
    return set(_WORD_RE.findall((s or "").lower()))


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def _csv_set(s: str | None) -> set[str]:
    return {x.strip() for x in (s or "").split(",") if x.strip()}


@dataclass
class DedupMatch:
    """Score breakdown for a single existing finding vs. a candidate."""
    finding_id: str
    score: float
    reasons: tuple[str, ...]


def score(candidate: dict[str, Any], existing: Finding) -> DedupMatch:
    """Weighted similarity score in [0, 1]."""
    s = 0.0
    weight_total = 0.0
    reasons: list[str] = []

    # Host match (weight 0.20) — strong signal
    cand_host = _norm(candidate.get("host"))
    if cand_host and existing.host and cand_host == _norm(existing.host):
        s += 0.20; reasons.append("same host")
    weight_total += 0.20

    # Port match (weight 0.10)
    if candidate.get("port") and existing.port and int(candidate["port"]) == int(existing.port):
        s += 0.10; reasons.append("same port")
    weight_total += 0.10

    # CVE overlap (weight 0.25) — very strong if both have CVEs
    cves_a = _csv_set(candidate.get("cve_ids"))
    cves_b = _csv_set(existing.cve_ids)
    if cves_a and cves_b and (cves_a & cves_b):
        s += 0.25; reasons.append(f"shared CVE: {', '.join(sorted(cves_a & cves_b))}")
    weight_total += 0.25

    # MITRE technique (weight 0.10)
    if (candidate.get("mitre_technique")
            and existing.mitre_technique
            and _norm(candidate["mitre_technique"]) == _norm(existing.mitre_technique)):
        s += 0.10; reasons.append("same MITRE technique")
    weight_total += 0.10

    # Title similarity (weight 0.25)
    r_title = _ratio(_norm(candidate.get("title")), _norm(existing.title))
    s += 0.25 * r_title
    if r_title > 0.85:
        reasons.append(f"title {int(r_title*100)}% similar")
    weight_total += 0.25

    # Description / token overlap (weight 0.10)
    toks_a = _tokens(candidate.get("description"))
    toks_b = _tokens(existing.description)
    if toks_a and toks_b:
        overlap = len(toks_a & toks_b) / max(1, len(toks_a | toks_b))
        s += 0.10 * overlap
    weight_total += 0.10

    final = s / weight_total if weight_total else 0.0
    return DedupMatch(finding_id=existing.id, score=round(final, 3), reasons=tuple(reasons))


def find_duplicates(
    workspace_id: str,
    candidate: dict[str, Any],
    *,
    threshold: float = 0.85,
    exclude_finding_id: str | None = None,
    limit: int = 5,
) -> list[DedupMatch]:
    """Find existing findings in the workspace that look like the candidate.

    Returns matches with score >= threshold, sorted by score desc, up to `limit`.
    """
    with get_session() as s:
        rows = s.execute(
            select(Finding)
            .join(Scan, Finding.scan_id == Scan.id)
            .where(Scan.workspace_id == workspace_id)
        ).scalars().all()
        results: list[DedupMatch] = []
        for existing in rows:
            if exclude_finding_id and existing.id == exclude_finding_id:
                continue
            m = score(candidate, existing)
            if m.score >= threshold:
                results.append(m)
        results.sort(key=lambda x: -x.score)
        return results[:limit]
