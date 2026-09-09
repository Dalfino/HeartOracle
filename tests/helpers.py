"""Shared offline test helpers: fake LLM, mock model install, study zip."""

from __future__ import annotations

import io
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

from make_mock_onnx import mock_meta
from make_synthetic_dicom import HU_CAVITY
from oracle.rag.kb_build import HashEmbedder
from oracle.rag.kb_build import build as kb_build
from oracle.rag.retrieve import Chunk
from oracle.synth.prompt import (
    DISCLAIMER,
    LOW_CONFIDENCE_BANNER,
    SECTION_HEADERS,
)

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES = TESTS_DIR / "fixtures"


def install_mock_model(model_dir: Path) -> Path:
    """Copy the committed tiny_seg.onnx + meta into *model_dir* as seg.onnx."""
    model_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / "tiny_seg.onnx", model_dir / "seg.onnx")
    (model_dir / "meta.json").write_text(json.dumps(mock_meta()), encoding="utf-8")
    return model_dir


def build_kb(kb_dir: Path, embedder: Any = None) -> Path:
    kb_dir.mkdir(parents=True, exist_ok=True)
    kb_build(FIXTURES / "mini_guidelines", kb_dir, embedder=embedder or HashEmbedder())
    return kb_dir


def make_study_zip(study_dir: Path, out_path: Path) -> Path:
    with zipfile.ZipFile(out_path, "w") as zf:
        for f in sorted(study_dir.rglob("*.dcm")):
            zf.write(f, arcname=f.name)
    return out_path


def make_zip_bytes(study_dir: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for f in sorted(study_dir.rglob("*.dcm")):
            zf.write(f, arcname=f.name)
    return buf.getvalue()


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


def fake_llm_of(builder: Any = compliant_report) -> Any:
    """Fake LLM: parses the JSON payload from the user message, drafts via *builder*."""

    def call(messages: list[dict[str, str]]) -> str:
        user_parts = [m["content"] for m in messages if m["role"] == "user"]
        blob = "\n\n".join(user_parts)
        payload = json.loads(blob[: blob.rindex("}") + 1])
        chunks = [
            Chunk(
                text=ch["text"],
                guideline_id=ch["guideline_id"],
                evidence_level=ch["evidence_level"],
                score=1.0,
            )
            for ch in payload["retrieved_guideline_chunks"]
        ]
        return builder(payload["segmentation"], payload["physics"], chunks)

    return call


__all__ = [
    "HU_CAVITY",
    "TESTS_DIR",
    "build_kb",
    "compliant_report",
    "fake_llm_of",
    "install_mock_model",
    "make_study_zip",
    "make_zip_bytes",
]
