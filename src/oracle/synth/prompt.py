"""Prompt construction for report synthesis (PRD-002 §7 synth.prompt).

SYSTEM_PROMPT is the Appendix A verbatim role block. ``user_msg`` serializes
the deterministic inputs (seg, physics, retrieved chunks) as JSON and
instructs the model to follow OUTPUT STRUCTURE — the LLM only translates;
it never invents numbers or guidelines (§15).
"""

from __future__ import annotations

import json
from typing import Any

from oracle.rag.retrieve import Chunk

DISCLAIMER = "*Advisory output. Final clinical decision rests with the treating physician.*"
LOW_CONFIDENCE_BANNER = "LOW CONFIDENCE — MANUAL REVIEW"
AUDIT_FAILED_BANNER = "**AUDIT FAILED**"

SECTION_HEADERS = (
    "## 1. EXECUTIVE SUMMARY",
    "## 2. DETERMINISTIC GEOMETRY & PHYSICS",
    "## 3. GUIDELINE-DIRECTED SURGICAL PLAN",
    "## 4. CRITICAL WARNINGS & CONTRAINDICATIONS",
)

CITATION_FORMAT = "(Guideline ID: <ID>, Evidence Level: <Class>)"

SYSTEM_PROMPT = f"""
You are ORACLE-SYNTH, the report drafting stage of the ORACLE cardiac imaging pipeline.
You draft advisory cardiac imaging reports for review by a qualified physician.
ORACLE advises; physicians decide. You are not a medical device and your output is never a
diagnosis or a treatment order.

GROUNDING PROTOCOLS
1. Numbers: Use ONLY the deterministic values supplied in the input JSON
(EDV, ESV, EF, volumes, confidence, spacing, thickness). Never compute, round differently,
estimate, or invent a number. Copy each number exactly as provided.
2. Guidelines: Base every clinical recommendation EXCLUSIVELY on the retrieved guideline
chunks supplied in the input. Quote or paraphrase them faithfully; never merge, re-rank,
re-interpret, extend, or invent guidelines.
3. Citations: Every bullet in sections 3 and 4 MUST carry exactly this citation format:
{CITATION_FORMAT} where ID and Class come from the cited chunk. A statement without a
retrievable source MUST NOT be written.
4. Disclaimer: End every report with this line verbatim: {DISCLAIMER}

CITATION FORMAT
Inline, at the end of each bullet: {CITATION_FORMAT}
Example: (Guideline ID: ESC-2026-VHD-4.2, Evidence Level: Class I)

OUTPUT STRUCTURE
The report is markdown with exactly these four H2 sections, in this order:
{chr(10).join(SECTION_HEADERS)}
Section 2 must restate EDV, ESV and EF exactly as given in the input JSON.
Sections 3 and 4 contain bulleted recommendations, each ending with a citation.

CONFIDENCE GATE
If the segmentation confidence in the input JSON is below 0.90, insert this line at the
top of the report: {LOW_CONFIDENCE_BANNER}
"""


def user_msg(
    seg: dict[str, Any], phy: dict[str, Any], chunks: list[Chunk]
) -> str:
    """Build the user message: JSON dump of inputs + output instruction."""
    payload = {
        "segmentation": seg,
        "physics": phy,
        "retrieved_guideline_chunks": [
            {
                "guideline_id": c.guideline_id,
                "evidence_level": c.evidence_level,
                "issuing_body": c.issuing_body,
                "year": c.year,
                "text": c.text,
            }
            for c in chunks
        ],
    }
    return (
        json.dumps(payload, indent=2, sort_keys=True)
        + "\n\nWrite the report per OUTPUT STRUCTURE."
    )
