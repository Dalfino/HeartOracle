"""Automated report auditor (PRD-002 §7 synth.auditor).

Checks, on the report draft vs. deterministic inputs:
(a) §2 numbers match inputs within ±0.05 (EDV, ESV, EF)
(b) citation regex on EVERY §3/§4 bullet
(c) cited guideline IDs ⊆ retrieved chunk IDs
(d) disclaimer line present as the final line
(e) confidence < 0.90 requires the LOW CONFIDENCE banner

Deviation from retrieved guidelines is a defect (§15): the auditor is the
mechanism that makes hallucinated citations or numbers impossible to ship.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from oracle.rag.retrieve import Chunk
from oracle.synth.prompt import (
    DISCLAIMER,
    LOW_CONFIDENCE_BANNER,
    SECTION_HEADERS,
)

CITATION_RE = re.compile(
    r"\(Guideline ID: ([A-Z]{2,4}-\d{4}-[A-Z]{2,4}-\d+(?:\.\d+)?), "
    r"Evidence Level: (Class I|Class IIa|Class IIb|Class III)\)"
)
_NUMBER_TOLERANCE = 0.05
_BULLET_RE = re.compile(r"^\s*[-*]\s+")


@dataclass
class AuditResult:
    passed: bool
    failures: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)

    def record(self, check: str, ok: bool, failure: str) -> None:
        self.checks[check] = ok
        if not ok:
            self.failures.append(failure)


def _sections(report: str) -> dict[str, str]:
    """Split the report on the four known H2 headers."""
    positions: list[tuple[str, int]] = []
    for header in SECTION_HEADERS:
        idx = report.find(header)
        if idx >= 0:
            positions.append((header, idx))
    positions.sort(key=lambda p: p[1])
    sections: dict[str, str] = {}
    for i, (header, start) in enumerate(positions):
        end = positions[i + 1][1] if i + 1 < len(positions) else len(report)
        sections[header] = report[start : end]
    return sections


def _bullets(section_text: str) -> list[str]:
    return [line.rstrip() for line in section_text.splitlines() if _BULLET_RE.match(line)]


def _extract_number(section_text: str, label: str) -> float | None:
    match = re.search(rf"{label}\D{{0,20}}?(-?\d+(?:\.\d+)?)", section_text)
    return float(match.group(1)) if match else None


def check_numbers(report: str, phy: dict[str, Any], result: AuditResult) -> None:
    section2 = _sections(report).get(SECTION_HEADERS[1], "")
    for label, expected in (
        ("EDV", float(phy["EDV_ml"])),
        ("ESV", float(phy["ESV_ml"])),
        ("EF", float(phy["ejection_fraction"])),
    ):
        found = _extract_number(section2, label)
        result.record(
            f"numbers_{label}",
            found is not None and abs(found - expected) <= _NUMBER_TOLERANCE,
            f"section 2 {label}: expected {expected}, found {found} (tol ±{_NUMBER_TOLERANCE})",
        )


def check_citations(report: str, chunks: list[Chunk], result: AuditResult) -> None:
    retrieved_ids = {c.guideline_id for c in chunks}
    sections = _sections(report)
    bullets = _bullets(sections.get(SECTION_HEADERS[2], "")) + _bullets(
        sections.get(SECTION_HEADERS[3], "")
    )
    cited_ids: set[str] = set()
    missing: list[int] = []
    for i, bullet in enumerate(bullets):
        matches = CITATION_RE.findall(bullet)
        if not matches:
            missing.append(i)
        cited_ids.update(gid for gid, _ in matches)
    result.record(
        "citation_coverage",
        not missing,
        f"sections 3/4 bullets without a valid citation: {missing}",
    )
    result.record(
        "cited_ids_subset",
        cited_ids.issubset(retrieved_ids),
        f"cited IDs not in retrieved set: {sorted(cited_ids - retrieved_ids)}",
    )


def check_disclaimer(report: str, result: AuditResult) -> None:
    last_line = report.strip().splitlines()[-1].strip() if report.strip() else ""
    result.record(
        "disclaimer",
        last_line == DISCLAIMER,
        f"report must end with the disclaimer line (found: {last_line[:60]!r})",
    )


def check_confidence(report: str, seg: dict[str, Any], result: AuditResult) -> None:
    confidence = float(seg.get("confidence", 1.0))
    if confidence < 0.90:
        result.record(
            "confidence_gate",
            LOW_CONFIDENCE_BANNER in report,
            f"confidence {confidence:.3f} < 0.90 requires banner {LOW_CONFIDENCE_BANNER!r}",
        )
    else:
        result.checks["confidence_gate"] = True


def audit(
    report: str, seg: dict[str, Any], phy: dict[str, Any], chunks: list[Chunk]
) -> AuditResult:
    """Run all checks; collect failures for the regeneration prompt."""
    result = AuditResult(passed=True)
    check_numbers(report, phy, result)
    check_citations(report, chunks, result)
    check_disclaimer(report, result)
    check_confidence(report, seg, result)
    result.passed = all(result.checks.values())
    return result
