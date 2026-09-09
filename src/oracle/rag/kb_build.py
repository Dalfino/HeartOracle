"""Guideline knowledge base builder (PRD-002 §7 rag.kb_build).

Parses guideline markdown with YAML frontmatter
(``guideline_id, issuing_body, year, evidence_level, context_tags[]``),
chunks bodies at 800 chars with 100-char overlap, embeds with
BAAI/bge-small-en-v1.5 (fastembed) — or an injected embedder for offline
tests — and stores everything in the Chroma collection ``oracle_guidelines``.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import yaml

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
COLLECTION_NAME = "oracle_guidelines"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


class Embedder(Protocol):
    """Minimal embedding interface: (n_texts) → (n, dim) L2-normalized float32."""

    dim: int

    def embed(self, texts: list[str]) -> np.ndarray: ...


class FastEmbedder:
    """Production embedder: BAAI/bge-small-en-v1.5 via fastembed (lazy import)."""

    def __init__(self, model_name: str = EMBED_MODEL) -> None:
        from fastembed import TextEmbedding  # noqa: PLC0415 - heavy, lazy

        self._model = TextEmbedding(model_name=model_name)
        self.dim = 384  # bge-small output dimensionality

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = np.asarray(list(self._model.embed(texts)), dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / np.clip(norms, 1e-9, None)


class HashEmbedder:
    """Deterministic offline embedder for tests: hashed char-trigrams, L2-normalized."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def _vec(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        normalized = re.sub(r"\s+", " ", text.lower()).strip()
        padded = f" {normalized} "
        for i in range(max(0, len(padded) - 2)):
            digest = hashlib.md5(padded[i : i + 3].encode("utf-8")).digest()
            vec[int.from_bytes(digest[:4], "little") % self.dim] += 1.0
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm > 0 else vec

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vec(t) for t in texts])


def parse_guideline(path: Path) -> dict[str, Any]:
    """Split a guideline markdown file into frontmatter metadata + body."""
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"guideline missing YAML frontmatter: {path}")
    meta = yaml.safe_load(match.group(1)) or {}
    for key in ("guideline_id", "issuing_body", "year", "evidence_level"):
        if key not in meta:
            raise ValueError(f"guideline frontmatter missing {key!r}: {path}")
    meta.setdefault("context_tags", [])
    meta["context_tags"] = [str(t) for t in meta["context_tags"]]
    meta["body"] = text[match.end() :].strip()
    return meta


def chunk_text(body: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Sliding-window chunking: *size* chars per chunk, *overlap* chars shared."""
    body = body.strip()
    if len(body) <= size:
        return [body] if body else []
    step = size - overlap
    chunks = [body[start : start + size] for start in range(0, len(body) - overlap, step)]
    return chunks


def _get_collection(kb_dir: str | Path):
    import chromadb  # noqa: PLC0415 - heavy, lazy

    client = chromadb.PersistentClient(path=str(kb_dir))
    return client.get_or_create_collection(
        name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )


def build(
    guidelines_dir: str | Path,
    kb_dir: str | Path,
    embedder: Embedder | None = None,
) -> int:
    """Index every guideline in *guidelines_dir*; return number of chunks stored."""
    embedder = embedder or FastEmbedder()
    docs = sorted(Path(guidelines_dir).glob("*.md"))
    if not docs:
        raise FileNotFoundError(f"no guideline .md files in {guidelines_dir}")

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []
    for doc in docs:
        meta = parse_guideline(doc)
        for i, chunk in enumerate(chunk_text(meta["body"])):
            ids.append(f"{meta['guideline_id']}::chunk{i}")
            documents.append(chunk)
            metadatas.append(
                {
                    "guideline_id": str(meta["guideline_id"]),
                    "issuing_body": str(meta["issuing_body"]),
                    "year": int(meta["year"]),
                    "evidence_level": str(meta["evidence_level"]),
                    "context_tags": ",".join(meta["context_tags"]),
                    "chunk_index": i,
                }
            )

    collection = _get_collection(kb_dir)
    if ids:
        existing = set(collection.get(ids=ids)["ids"])
        new = [
            (i, d, m)
            for i, d, m in zip(ids, documents, metadatas, strict=True)
            if i not in existing
        ]
        if new:
            vectors = embedder.embed([d for _, d, _ in new])
            collection.add(
                ids=[i for i, _, _ in new],
                documents=[d for _, d, _ in new],
                metadatas=[m for _, _, m in new],
                embeddings=vectors,
            )
    return len(ids)
