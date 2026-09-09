"""Gradio web UI (PRD-002 §7 ui.gradio_app).

Blocks: File(upload .zip) → Button Run → Markdown report + Textbox status;
footer disclaimer always visible. Gradio is imported lazily so the module
(and its testable pipeline helper) loads without the UI stack installed.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from oracle.api.main import _findings_from
from oracle.config import get_settings
from oracle.errors import OracleError
from oracle.physics.features import compute_physics
from oracle.rag.kb_build import default_embedder
from oracle.rag.retrieve import retrieve
from oracle.synth.report import LlmCallable, synthesize_report

DISCLAIMER_FOOTER = "ORACLE advises. Physicians decide. — research prototype, not for clinical use."


def run_study(
    zip_path: str,
    *,
    llm: LlmCallable | None = None,
    embedder: Any = None,
) -> tuple[str, str]:
    """Process an uploaded DICOM zip; return (report_markdown, status_text)."""
    from oracle.ingest.deidentify import deidentify  # noqa: PLC0415
    from oracle.ingest.dicom_io import load_study  # noqa: PLC0415
    from oracle.seg.onnx_infer import segment  # noqa: PLC0415

    settings = get_settings()
    work = Path(settings.data_dir) / "ui-upload"
    raw = work / "raw"
    anon = work / "anon"
    raw.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(raw)
    token = deidentify(raw, anon)
    study = load_study(anon)
    study["study_token"] = token

    seg = segment(study, settings.model_dir)
    phy = compute_physics(seg, study)
    chunks = retrieve(
        _findings_from(phy),
        str(settings.kb_dir),
        top_k=3,
        embedder=embedder or default_embedder(),
    )
    report, audit_result = synthesize_report(
        seg, phy, chunks, llm=llm, out_path=work / "report.md"
    )
    status = (
        f"done · study {token} · confidence {seg['confidence']:.3f} · "
        f"audit {'PASSED' if audit_result.passed else 'FAILED'}"
    )
    return report, status


def run_study_safe(zip_path: str, **kwargs: Any) -> tuple[str, str]:
    """run_study with user-facing error mapping (never raises to the UI)."""
    try:
        return run_study(zip_path, **kwargs)
    except OracleError as exc:
        return "", f"error {exc.code}: {exc.message}"
    except Exception as exc:  # noqa: BLE001
        return "", f"error: {exc}"


def build_app() -> Any:
    """Assemble the Gradio Blocks app (requires the `ui` extra)."""
    import gradio as gr  # noqa: PLC0415 - heavy, lazy

    with gr.Blocks(title="ORACLE — cardiac MR advisory draft") as demo:
        gr.Markdown(
            "# ORACLE\n"
            "Local-first cardiac MR analysis: upload a DICOM study (zip), run the "
            "pipeline, read the fully-cited advisory report draft."
        )
        file = gr.File(label="DICOM study (.zip)", file_types=[".zip"])
        btn = gr.Button("Run pipeline", variant="primary")
        status = gr.Textbox(label="Status", interactive=False)
        report = gr.Markdown(label="Report draft")
        btn.click(run_study_safe, inputs=[file], outputs=[report, status])
        gr.Markdown(f"---\n*{DISCLAIMER_FOOTER}*")
    return demo


def launch(port: int = 7860) -> None:  # pragma: no cover - requires gradio
    build_app().launch(server_name="0.0.0.0", server_port=port)
