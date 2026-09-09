"""Report synthesis + audit orchestration (PRD-002 §7 synth.report).

LLM contract: a callable ``(messages: list[dict]) -> str``. The production
LLM is a local GGUF via llama.cpp with pinned deterministic params
(temp=0.0, top_p=1.0, seed=42, n_threads=ORACLE_THREADS, n_ctx=4096,
max_tokens=1200). ``ORACLE_DEV_LLM=1`` permits the Groq dev fallback; the
production path never touches the network (§15).

Flow: generate → audit → (fail: regenerate once with failure notes) →
(audit fail again: write **AUDIT FAILED** banner report + raise E-SYN-002).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from oracle.config import get_settings
from oracle.errors import e_syn_001, e_syn_002
from oracle.rag.retrieve import Chunk
from oracle.synth.auditor import AuditResult, audit
from oracle.synth.prompt import AUDIT_FAILED_BANNER, DISCLAIMER, SYSTEM_PROMPT, user_msg

LlmCallable = Callable[[list[dict[str, str]]], str]


def llama_params() -> dict[str, Any]:
    """Pinned deterministic llama.cpp sampling params (§7)."""
    settings = get_settings()
    return {
        "temperature": 0.0,
        "top_p": 1.0,
        "seed": 42,
        "n_threads": settings.threads,
        "n_ctx": 4096,
        "max_tokens": 1200,
    }


def _load_local_llm() -> LlmCallable:
    """Load the local GGUF (lazy import) and return a messages→text callable."""
    settings = get_settings()
    path = Path(settings.llm_path)
    if not path.is_file():
        raise e_syn_001(
            "local LLM file not found (run tools/fetch_llm.sh or set ORACLE_LLM_PATH)",
            detail=str(path),
        )
    try:
        from llama_cpp import Llama  # noqa: PLC0415 - heavy, lazy

        params = llama_params()
        llm = Llama(
            model_path=str(path),
            n_threads=params["n_threads"],
            n_ctx=params["n_ctx"],
            seed=params["seed"],
            verbose=False,
        )

        def call(messages: list[dict[str, str]]) -> str:
            return str(
                llm.create_chat_completion(
                    messages=messages,
                    temperature=params["temperature"],
                    top_p=params["top_p"],
                    max_tokens=params["max_tokens"],
                )["choices"][0]["message"]["content"]
            )

        return call
    except Exception as exc:  # noqa: BLE001
        raise e_syn_001(f"failed to load local LLM: {exc}") from exc


def build_messages(
    seg: dict[str, Any],
    phy: dict[str, Any],
    chunks: list[Chunk],
    *,
    failure_notes: list[str] | None = None,
) -> list[dict[str, str]]:
    """System + user messages; on regeneration, failure notes are appended."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg(seg, phy, chunks)},
    ]
    if failure_notes:
        notes = "\n".join(f"- {note}" for note in failure_notes)
        messages.append(
            {
                "role": "user",
                "content": (
                    "The previous draft FAILED the automated audit for these reasons:\n"
                    f"{notes}\n\nRegenerate the report, fixing every listed failure. "
                    "Follow OUTPUT STRUCTURE and Grounding Protocols exactly."
                ),
            }
        )
    return messages


def generate(
    seg: dict[str, Any],
    phy: dict[str, Any],
    chunks: list[Chunk],
    *,
    llm: LlmCallable | None = None,
    failure_notes: list[str] | None = None,
) -> str:
    """One report draft from the LLM (local GGUF by default)."""
    if llm is None and get_settings().dev_llm:
        llm = _dev_llm()
    call = llm or _load_local_llm()
    return call(build_messages(seg, phy, chunks, failure_notes=failure_notes)).strip()


def _dev_llm() -> LlmCallable:
    """Groq dev fallback (ORACLE_DEV_LLM=1 only; never in production path)."""
    import os  # noqa: PLC0415

    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise e_syn_001("ORACLE_DEV_LLM=1 but GROQ_API_KEY is not set")

    def call(messages: list[dict[str, str]]) -> str:
        import urllib.request  # noqa: PLC0415 - dev only

        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(
                {
                    "model": os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
                    "messages": messages,
                    "temperature": 0.0,
                    "seed": 42,
                }
            ).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
            body = json.loads(resp.read().decode())
        return str(body["choices"][0]["message"]["content"])

    return call


def synthesize_report(
    seg: dict[str, Any],
    phy: dict[str, Any],
    chunks: list[Chunk],
    *,
    llm: LlmCallable | None = None,
    out_path: str | Path | None = None,
) -> tuple[str, AuditResult]:
    """Generate → audit → regenerate-once → audit. Raise E-SYN-002 on repeat fail.

    On a second audit failure the report is still written with an
    **AUDIT FAILED** banner so the operator sees the draft; exit code 5 is
    then propagated by the CLI from the raised error.
    """
    first = generate(seg, phy, chunks, llm=llm)
    result = audit(first, seg, phy, chunks)
    if result.passed:
        _write(out_path, first)
        return first, result

    retry = generate(seg, phy, chunks, llm=llm, failure_notes=result.failures)
    second = audit(retry, seg, phy, chunks)
    if second.passed:
        _write(out_path, retry)
        return retry, second

    bannered = f"{AUDIT_FAILED_BANNER}\n\n{retry}\n\n{AUDIT_FAILED_BANNER}"
    _write(out_path, bannered)
    raise e_syn_002(f"report failed audit twice: {second.failures}")


def _write(out_path: str | Path | None, text: str) -> None:
    if out_path is not None:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")


__all__ = [
    "DISCLAIMER",
    "LlmCallable",
    "audit",
    "build_messages",
    "generate",
    "llama_params",
    "synthesize_report",
]
