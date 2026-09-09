"""Guideline retrieval (PRD-002 §7 rag.retrieve).

Query template: "cardiac {modality} EF {ef} {abnormal findings} management
recommendation". Returns top_k Chunk records with cosine score ≥ min_score
(default 0.25). Guardrails (§15): the retrieved set is authoritative — no
re-ranking beyond similarity, no guideline invention.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from oracle.errors import e_rag_001, e_rag_002
from oracle.rag.kb_build import Embedder, FastEmbedder, _get_collection


@dataclass
class Chunk:
    text: str
    guideline_id: str
    evidence_level: str
    score: float
    issuing_body: str = ""
    year: int = 0
    context_tags: list[str] = field(default_factory=list)

    def citation(self) -> str:
        """Canonical inline citation used by the auditor's §8 regex."""
        return f"(Guideline ID: {self.guideline_id}, Evidence Level: {self.evidence_level})"


def build_query(findings: dict[str, Any]) -> str:
    """Compose the retrieval query from a findings dict (§7 template)."""
    modality = findings.get("modality", "MR")
    ef = findings.get("ejection_fraction", "n/a")
    abnormal = findings.get("abnormal_findings", "") or ""
    return f"cardiac {modality} EF {ef} {abnormal} management recommendation"


def retrieve(
    findings: dict[str, Any],
    kb_dir: str,
    top_k: int = 3,
    min_score: float = 0.25,
    embedder: Embedder | None = None,
) -> list[Chunk]:
    """Retrieve the top-k guideline chunks matching *findings*."""
    embedder = embedder or FastEmbedder()
    collection = _get_collection(kb_dir)
    count = collection.count()
    if count == 0:
        raise e_rag_001("knowledge base is empty (run `oracle kb build` first)")

    query_text = build_query(findings)
    vector = embedder.embed([query_text])[0]
    k = max(1, min(top_k, count))
    result = collection.query(query_embeddings=[vector.tolist()], n_results=k)

    chunks: list[Chunk] = []
    for i, doc_id in enumerate(result["ids"][0]):
        meta = (result.get("metadatas") or [[]])[0][i] or {}
        distance = (result.get("distances") or [[]])[0][i]
        score = 1.0 - float(distance) if distance is not None else 0.0
        if score < min_score:
            continue
        chunks.append(
            Chunk(
                text=result["documents"][0][i],
                guideline_id=str(meta.get("guideline_id", doc_id.split("::")[0])),
                evidence_level=str(meta.get("evidence_level", "Class IIb")),
                score=round(score, 4),
                issuing_body=str(meta.get("issuing_body", "")),
                year=int(meta.get("year", 0)),
                context_tags=[t for t in str(meta.get("context_tags", "")).split(",") if t],
            )
        )
    if not chunks:
        distances = (result.get("distances") or [[]])[0]
        best = max((1.0 - float(d) for d in distances), default=0.0)
        raise e_rag_002(f"no retrieved chunk reached min_score {min_score} (best {best:.3f})")
    return chunks
