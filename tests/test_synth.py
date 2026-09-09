"""Phase 5 acceptance tests: synthesis + audit gate (PRD-002 §9 P5).

Offline: the LLM is injected as a deterministic fake that drafts a
spec-compliant report from the JSON inputs. The audit gate — the component
that makes hallucinated numbers/citations impossible to ship — is exercised
positively and negatively.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from oracle.errors import SynthError
from oracle.rag.kb_build import HashEmbedder, build
from oracle.rag.retrieve import Chunk, retrieve
from oracle.synth.auditor import CITATION_RE, audit
from oracle.synth.prompt import (
    DISCLAIMER,
    LOW_CONFIDENCE_BANNER,
    SECTION_HEADERS,
    SYSTEM_PROMPT,
    user_msg,
)
from oracle.synth.report import generate, llama_params, synthesize_report

FIXTURE_KB = Path(__file__).resolve().parent / "fixtures" / "mini_guidelines"


def make_chunks(n: int = 2) -> list[Chunk]:
    return [
        Chunk(
            text="recommendation chunk",
            guideline_id="ESC-2026-VHD-4.2",
            evidence_level="Class I",
            score=0.6,
        ),
        Chunk(
            text="warning chunk",
            guideline_id="ACC-2025-PCI-7.1",
            evidence_level="Class IIa",
            score=0.4,
        ),
    ][:n]


def make_seg(confidence: float = 0.97) -> dict[str, Any]:
    return {"study_token": "a" * 12, "confidence": confidence}


def make_phy() -> dict[str, Any]:
    return {"EDV_ml": 118.0, "ESV_ml": 53.0, "ejection_fraction": 55.08}


def compliant_report(seg: dict[str, Any], phy: dict[str, Any], chunks: list[Chunk]) -> str:
    """A draft satisfying every audit check (what a good LLM must produce)."""
    lines: list[str] = []
    if float(seg.get("confidence", 1.0)) < 0.90:
        lines.append(LOW_CONFIDENCE_BANNER)
        lines.append("")
    lines.append(SECTION_HEADERS[0])
    lines.append(
        f"LV volumetrics from cine MR: EDV {phy['EDV_ml']:.2f} ml, "
        f"ESV {phy['ESV_ml']:.2f} ml, EF {phy['ejection_fraction']:.2f} percent."
    )
    lines.append("")
    lines.append(SECTION_HEADERS[1])
    lines.append(f"- EDV: {phy['EDV_ml']:.2f} ml")
    lines.append(f"- ESV: {phy['ESV_ml']:.2f} ml")
    lines.append(f"- EF: {phy['ejection_fraction']:.2f} percent")
    lines.append("")
    lines.append(SECTION_HEADERS[2])
    for c in chunks:
        lines.append(f"- Follow {c.guideline_id} guidance {c.citation()}")
    lines.append("")
    lines.append(SECTION_HEADERS[3])
    for c in chunks:
        lines.append(f"- Verify contraindications per {c.guideline_id} {c.citation()}")
    lines.append("")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def fake_llm_of(builder=compliant_report) -> Any:
    """Fake LLM: parses the JSON payload from the user message, drafts via *builder*."""

    def call(messages: list[dict[str, str]]) -> str:
        user_parts = [m["content"] for m in messages if m["role"] == "user"]
        blob = "\n\n".join(user_parts)
        payload = json.loads(blob[: blob.rindex("}") + 1])
        return builder(payload["segmentation"], payload["physics"], [
            Chunk(
                text=ch["text"],
                guideline_id=ch["guideline_id"],
                evidence_level=ch["evidence_level"],
                score=1.0,
            )
            for ch in payload["retrieved_guideline_chunks"]
        ])

    return call


class TestPrompt:
    def test_system_prompt_structure(self) -> None:
        for header in SECTION_HEADERS:
            assert header in SYSTEM_PROMPT
        assert "Grounding" in SYSTEM_PROMPT or "GROUNDING" in SYSTEM_PROMPT
        assert DISCLAIMER in SYSTEM_PROMPT
        assert "LOW CONFIDENCE" in SYSTEM_PROMPT

    def test_user_msg_json_and_instruction(self) -> None:
        msg = user_msg(make_seg(), make_phy(), make_chunks())
        assert msg.endswith("Write the report per OUTPUT STRUCTURE.")
        payload = json.loads(msg[: msg.rindex("}") + 1])
        assert payload["physics"]["EDV_ml"] == 118.0
        assert payload["retrieved_guideline_chunks"][0]["guideline_id"] == "ESC-2026-VHD-4.2"


class TestAudit:
    def test_compliant_report_passes(self) -> None:
        report = compliant_report(make_seg(), make_phy(), make_chunks())
        result = audit(report, make_seg(), make_phy(), make_chunks())
        assert result.passed, result.failures

    def test_number_mismatch_rejected(self) -> None:
        """PRD P5 negative AC: injected EF 99 → auditor rejects."""
        phy = make_phy()
        bad_phy = {**phy, "ejection_fraction": 99.0}
        seg = make_seg()
        report = compliant_report(seg, bad_phy, make_chunks())
        result = audit(report, seg, phy, make_chunks())
        assert not result.passed
        assert any("EF" in f for f in result.failures)

    def test_edv_mismatch_rejected(self) -> None:
        seg, phy, chunks = make_seg(), make_phy(), make_chunks()
        report = compliant_report(seg, phy, chunks).replace("118.00", "120.00")
        result = audit(report, seg, phy, chunks)
        assert not result.passed

    def test_bullet_without_citation_rejected(self) -> None:
        seg, phy = make_seg(), make_phy()
        report = compliant_report(seg, phy, make_chunks()).replace(
            " guidance (Guideline ID: ESC-2026-VHD-4.2, Evidence Level: Class I)", " guidance"
        )
        result = audit(report, seg, phy, make_chunks())
        assert not result.passed
        assert any("citation" in f for f in result.failures)

    def test_uncited_guideline_id_rejected(self) -> None:
        seg, phy = make_seg(), make_phy()
        report = compliant_report(seg, phy, make_chunks()).replace(
            "ESC-2026-VHD-4.2", "ESC-2099-XXX-9.9"
        )
        result = audit(report, seg, phy, make_chunks())
        assert not result.passed
        assert any("not in retrieved" in f for f in result.failures)

    def test_missing_disclaimer_rejected(self) -> None:
        seg, phy, chunks = make_seg(), make_phy(), make_chunks()
        report = "\n".join(compliant_report(seg, phy, chunks).splitlines()[:-1])
        result = audit(report, seg, phy, chunks)
        assert not result.passed
        assert any("disclaimer" in f for f in result.failures)

    def test_low_confidence_requires_banner(self) -> None:
        seg = make_seg(confidence=0.72)
        with_banner = compliant_report(seg, make_phy(), make_chunks())
        assert audit(with_banner, seg, make_phy(), make_chunks()).passed

        without_banner = "\n".join(
            line for line in with_banner.splitlines() if line != LOW_CONFIDENCE_BANNER
        ).replace("\n\n\n", "\n\n")
        result = audit(without_banner, seg, make_phy(), make_chunks())
        assert not result.passed
        assert any("confidence" in f for f in result.failures)

    def test_high_confidence_no_banner_needed(self) -> None:
        seg, phy, chunks = make_seg(confidence=0.97), make_phy(), make_chunks()
        report = compliant_report(seg, phy, chunks)
        assert LOW_CONFIDENCE_BANNER not in report
        assert audit(report, seg, phy, chunks).passed

    def test_citation_regex_rejects_invalid_evidence_level(self) -> None:
        bad = "(Guideline ID: ESC-2026-VHD-4.2, Evidence Level: Class V)"
        assert CITATION_RE.findall(bad) == []

    def test_citation_regex_accepts_decimal_section(self) -> None:
        good = "(Guideline ID: ACC-2025-PCI-7.1, Evidence Level: Class IIa)"
        assert CITATION_RE.findall(good) == [("ACC-2025-PCI-7.1", "Class IIa")]


class TestReportGeneration:
    def test_generate_with_fake_llm(self) -> None:
        report = generate(make_seg(), make_phy(), make_chunks(), llm=fake_llm_of())
        for header in SECTION_HEADERS:
            assert header in report
        assert report.endswith(DISCLAIMER)

    def test_generate_passes_failure_notes_on_retry(self) -> None:
        seen: list[list[dict[str, str]]] = []

        def spy(messages: list[dict[str, str]]) -> str:
            seen.append(messages)
            return compliant_report(make_seg(), make_phy(), make_chunks())

        generate(make_seg(), make_phy(), make_chunks(), llm=spy, failure_notes=["bad numbers"])
        assert len(seen) == 1
        assert any("bad numbers" in m["content"] for m in seen[0] if m["role"] == "user")

    def test_llama_params_deterministic(self) -> None:
        params = llama_params()
        assert params["temperature"] == 0.0
        assert params["top_p"] == 1.0
        assert params["seed"] == 42
        assert params["n_ctx"] == 4096
        assert params["max_tokens"] == 1200
        assert params["n_threads"] == 4

    def test_synthesize_passes_through(self, tmp_path: Path) -> None:
        out = tmp_path / "report.md"
        report, result = synthesize_report(
            make_seg(), make_phy(), make_chunks(), llm=fake_llm_of(), out_path=out
        )
        assert result.passed
        assert out.read_text(encoding="utf-8").strip() == report.strip()

    def test_synthesize_retries_once_then_banners_and_raises(self, tmp_path: Path) -> None:
        """PRD P5: fail → regenerate once → fail → E-SYN-002 + banner + exit 5."""
        out = tmp_path / "report.md"

        def always_bad(seg: Any, phy: Any, chunks: Any) -> str:
            return "## 1. EXECUTIVE SUMMARY\ngarbage without citations\n"

        calls: list[int] = []

        def llm(messages: list[dict[str, str]]) -> str:
            calls.append(1)
            return always_bad(None, None, None)  # type: ignore[arg-type]

        with pytest.raises(SynthError) as err:
            synthesize_report(make_seg(), make_phy(), make_chunks(), llm=llm, out_path=out)
        assert err.value.code == "E-SYN-002"
        assert err.value.exit_code == 5
        assert len(calls) == 2  # exactly one regeneration
        text = out.read_text(encoding="utf-8")
        assert text.startswith("**AUDIT FAILED**")
        assert text.rstrip().endswith("**AUDIT FAILED**")

    def test_synthesize_retry_can_recover(self, tmp_path: Path) -> None:
        out = tmp_path / "report.md"
        state = {"n": 0}

        def llm_first_bad(messages: list[dict[str, str]]) -> str:
            state["n"] += 1
            if state["n"] == 1:
                return "## 1. EXECUTIVE SUMMARY\nbroken draft\n"
            return compliant_report(make_seg(), make_phy(), make_chunks())

        report, result = synthesize_report(
            make_seg(), make_phy(), make_chunks(), llm=llm_first_bad, out_path=out
        )
        assert result.passed
        assert state["n"] == 2
        assert "**AUDIT FAILED**" not in out.read_text(encoding="utf-8")
        assert report.endswith(DISCLAIMER)


class TestRealRetrievalIntoPrompt:
    def test_pipeline_chunks_format_for_prompt(self, tmp_path: Path) -> None:
        build(FIXTURE_KB, tmp_path / "kb", embedder=HashEmbedder())
        chunks = retrieve(
            {
                "modality": "MR",
                "ejection_fraction": 55.08,
                "abnormal_findings": "severe aortic stenosis annulus 28 mm",
            },
            str(tmp_path / "kb"),
            embedder=HashEmbedder(),
        )
        msg = user_msg(make_seg(), make_phy(), chunks)
        payload = json.loads(msg[: msg.rindex("}") + 1])
        assert payload["retrieved_guideline_chunks"], "chunks must serialize into the prompt"
