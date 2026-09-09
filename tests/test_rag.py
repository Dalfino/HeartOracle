"""Phase 4 acceptance tests: guideline RAG (PRD-002 §9 P4).

Offline by design: the deterministic HashEmbedder stands in for
BAAI/bge-small-en-v1.5, which requires a one-time model download (asset
fetch, like the GGUF — see README "Fetch assets"). The fastembed path is
exercised by the optional test at the bottom when the package is present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from oracle.errors import RagError
from oracle.rag.kb_build import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    HashEmbedder,
    build,
    chunk_text,
    parse_guideline,
)
from oracle.rag.retrieve import build_query, retrieve

FIXTURE_KB = Path(__file__).resolve().parent / "fixtures" / "mini_guidelines"


@pytest.fixture()
def kb_dir(tmp_path: Path) -> Path:
    out = tmp_path / "kb"
    build(FIXTURE_KB, out, embedder=HashEmbedder())
    return out


class TestKbBuild:
    def test_build_indexes_all_documents(self, kb_dir: Path) -> None:
        from oracle.rag.kb_build import _get_collection

        n_docs = len(list(FIXTURE_KB.glob("*.md")))
        assert _get_collection(str(kb_dir)).count() >= n_docs

    def test_build_is_incremental(self, kb_dir: Path) -> None:
        from oracle.rag.kb_build import _get_collection

        before = _get_collection(str(kb_dir)).count()
        n = build(FIXTURE_KB, kb_dir, embedder=HashEmbedder())
        assert n == before  # re-build adds nothing new

    def test_frontmatter_parsed(self) -> None:
        meta = parse_guideline(FIXTURE_KB / "ESC-2026-VHD-4.2.md")
        assert meta["guideline_id"] == "ESC-2026-VHD-4.2"
        assert meta["issuing_body"] == "ESC"
        assert meta["year"] == 2026
        assert meta["evidence_level"] == "Class I"
        assert "valve" in meta["context_tags"]

    def test_frontmatter_missing_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.md"
        bad.write_text("no frontmatter here", encoding="utf-8")
        with pytest.raises(ValueError, match="frontmatter"):
            parse_guideline(bad)

    def test_chunking_800_100(self) -> None:
        body = "x" * 2000
        chunks = chunk_text(body)
        assert len(chunks) == 3  # windows at 0, 700, 1400 (tail chunk shorter)
        assert all(len(c) <= CHUNK_SIZE for c in chunks)
        assert len(chunks[0]) == CHUNK_SIZE
        assert chunks[0][CHUNK_SIZE - CHUNK_OVERLAP :] == chunks[1][:CHUNK_OVERLAP]

    def test_chunking_short_body_single_chunk(self) -> None:
        assert chunk_text("short body") == ["short body"]

    def test_chunking_empty(self) -> None:
        assert chunk_text("") == []


class TestRetrieve:
    FINDINGS = {
        "modality": "MR",
        "ejection_fraction": 55.1,
        "abnormal_findings": "severe aortic stenosis annulus 28 mm",
    }

    def test_seeded_query_returns_vhd_in_top3(self, kb_dir: Path) -> None:
        """PRD P4 AC: seeded query returns ESC-2026-VHD-4.2 in top-3, score ≥ 0.25."""
        chunks = retrieve(self.FINDINGS, str(kb_dir), top_k=3, embedder=HashEmbedder())
        ids = [c.guideline_id for c in chunks]
        assert "ESC-2026-VHD-4.2" in ids
        assert all(c.score >= 0.25 for c in chunks)

    def test_top_k_respected(self, kb_dir: Path) -> None:
        chunks = retrieve(self.FINDINGS, str(kb_dir), top_k=3, embedder=HashEmbedder())
        assert 1 <= len(chunks) <= 3

    def test_chunk_carries_metadata(self, kb_dir: Path) -> None:
        chunks = retrieve(self.FINDINGS, str(kb_dir), top_k=3, embedder=HashEmbedder())
        c = chunks[0]
        assert c.evidence_level.startswith("Class ")
        assert c.text
        assert c.citation().startswith("(Guideline ID: ")

    def test_empty_kb_raises_e_rag_001(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty-kb"
        empty.mkdir()
        with pytest.raises(RagError) as err:
            retrieve(self.FINDINGS, str(empty), embedder=HashEmbedder())
        assert err.value.code == "E-RAG-001"

    def test_no_chunk_above_threshold_raises_e_rag_002(self, kb_dir: Path) -> None:
        with pytest.raises(RagError) as err:
            retrieve(
                {"modality": "ZZ", "ejection_fraction": 0.0, "abnormal_findings": "qqq www zzz"},
                str(kb_dir),
                top_k=3,
                min_score=0.999,
                embedder=HashEmbedder(),
            )
        assert err.value.code == "E-RAG-002"

    def test_query_template(self) -> None:
        q = build_query(
            {"modality": "CT", "ejection_fraction": 34.0, "abnormal_findings": "calcification"}
        )
        assert q == "cardiac CT EF 34.0 calcification management recommendation"


def test_fastembed_path_when_available() -> None:
    """Optional: real bge-small embedder (requires fastembed + cached model)."""
    pytest.importorskip("fastembed")
    from oracle.rag.kb_build import FastEmbedder

    emb = FastEmbedder()
    vecs = emb.embed(["cardiac MR volumetrics", "totally unrelated text"])
    assert vecs.shape == (2, emb.dim)
