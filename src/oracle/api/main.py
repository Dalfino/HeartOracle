"""FastAPI service (PRD-002 §7 api.main).

POST /api/v1/studies   (multipart zip of DICOMs) → 202 {"study_id"}
GET  /api/v1/studies/{id}            → {"status": queued|running|done|failed}
GET  /api/v1/studies/{id}/report     → {"markdown": ...} when done
Error envelope: {"error": {"code", "message"}}; 404 unknown study,
413 upload too large, 422 not a DICOM zip, 409 report not ready.

The pipeline executor is injectable: ``create_app(llm=...)`` lets tests run
the full flow offline (fake LLM); production uses the local GGUF path.
"""

from __future__ import annotations

import io
import json
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, UploadFile
from fastapi.responses import JSONResponse

from oracle import __version__
from oracle.config import get_settings
from oracle.errors import OracleError
from oracle.physics.features import compute_physics
from oracle.rag.kb_build import default_embedder
from oracle.rag.retrieve import retrieve
from oracle.synth.report import LlmCallable, synthesize_report

MAX_UPLOAD_BYTES = 512 * 1024 * 1024


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Canonical §12-style error envelope."""
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


@dataclass
class Job:
    status: str = "queued"
    report: str | None = None
    error: dict[str, str] | None = None
    timeline: list[dict[str, Any]] = field(default_factory=list)


def _findings_from(phy: dict[str, Any]) -> dict[str, Any]:
    ef = float(phy["ejection_fraction"])
    abnormal = "reduced ejection fraction" if ef < 40.0 else "preserved ejection fraction"
    return {
        "modality": phy.get("modality", "MR"),
        "ejection_fraction": ef,
        "abnormal_findings": abnormal,
    }


def run_pipeline(
    zip_bytes: bytes,
    study_id: str,
    job: Job,
    *,
    llm: LlmCallable | None = None,
    embedder: Any = None,
) -> None:
    """Full ingest→segment→physics→RAG→report flow; updates *job* in place."""
    from oracle.ingest.deidentify import deidentify  # noqa: PLC0415 - avoid import cycle
    from oracle.ingest.dicom_io import load_study  # noqa: PLC0415
    from oracle.seg.onnx_infer import segment  # noqa: PLC0415

    settings = get_settings()
    data_dir = Path(settings.data_dir) / study_id
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    try:
        job.status = "running"
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(raw_dir)

        token = deidentify(raw_dir, data_dir / "anon")
        study = load_study(data_dir / "anon")
        study["study_token"] = token

        t0 = time.perf_counter()
        seg = segment(study, settings.model_dir)
        job.timeline.append({"stage": "segment", "ms": int((time.perf_counter() - t0) * 1000)})

        phy = compute_physics(seg, study)

        kb_dir = Path(settings.kb_dir)
        if not kb_dir.exists() or not any(kb_dir.iterdir()):
            raise OracleError(
                "knowledge base not built; run `oracle kb build` first", code="E-RAG-001"
            )
        t0 = time.perf_counter()
        chunks = retrieve(
            _findings_from(phy),
            str(kb_dir),
            top_k=3,
            embedder=embedder or default_embedder(),
        )
        job.timeline.append({"stage": "retrieve", "ms": int((time.perf_counter() - t0) * 1000)})

        t0 = time.perf_counter()
        report, audit_result = synthesize_report(
            seg, phy, chunks, llm=llm, out_path=data_dir / "report.md"
        )
        job.timeline.append({"stage": "report", "ms": int((time.perf_counter() - t0) * 1000)})

        if not audit_result.passed:  # unreachable: synthesize_report raises; belt & braces
            raise OracleError("report audit failed", code="E-SYN-002")
        (data_dir / "seg.json").write_text(json.dumps(seg, indent=2), encoding="utf-8")
        (data_dir / "phy.json").write_text(json.dumps(phy, indent=2), encoding="utf-8")
        # additive: persist retrieval evidence for the dashboard (not in §6 contract)
        (data_dir / "chunks.json").write_text(
            json.dumps(
                [
                    {
                        "guideline_id": c.guideline_id,
                        "evidence_level": c.evidence_level,
                        "score": round(c.score, 4),
                        "issuing_body": c.issuing_body,
                        "year": c.year,
                        "text": c.text[:400],
                    }
                    for c in chunks
                ],
                indent=2,
            ),
            encoding="utf-8",
        )
        job.report = report
        job.status = "done"
    except OracleError as exc:
        job.error = exc.to_dict()
        job.status = "failed"
    except Exception as exc:  # noqa: BLE001 - surface unexpected failures in the API
        job.error = {"code": "E-ORC-500", "message": str(exc)}
        job.status = "failed"


def create_app(
    llm: LlmCallable | None = None,
    *,
    embedder: Any = None,
    max_upload_bytes: int = MAX_UPLOAD_BYTES,
    executor: ThreadPoolExecutor | None = None,
) -> FastAPI:
    app = FastAPI(title="ORACLE", version=__version__, docs_url="/docs")
    jobs: dict[str, Job] = {}
    pool = executor or ThreadPoolExecutor(max_workers=2)

    @app.post("/api/v1/studies")
    async def create_study(file: UploadFile) -> JSONResponse:
        data = await file.read()
        if len(data) > max_upload_bytes:
            return error_response(413, "E-API-413", f"upload exceeds {max_upload_bytes} bytes")
        if not zipfile.is_zipfile(io.BytesIO(data)):
            return error_response(422, "E-API-422", "upload must be a zip archive of DICOM files")

        study_id = uuid.uuid4().hex[:12]
        jobs[study_id] = Job()
        pool.submit(run_pipeline, data, study_id, jobs[study_id], llm=llm, embedder=embedder)
        return JSONResponse(status_code=202, content={"study_id": study_id})

    @app.get("/api/v1/studies/{study_id}")
    async def study_status(study_id: str) -> JSONResponse:
        job = jobs.get(study_id)
        if job is None:
            return error_response(404, "E-API-404", f"unknown study {study_id!r}")
        return JSONResponse(
            status_code=200,
            content={
                "study_id": study_id,
                "status": job.status,
                "error": job.error,
                # additive: progress timeline for operators/UI (not in §6 contract)
                "timeline": job.timeline,
            },
        )

    @app.get("/api/v1/studies/{study_id}/report")
    async def study_report(study_id: str) -> JSONResponse:
        job = jobs.get(study_id)
        if job is None:
            return error_response(404, "E-API-404", f"unknown study {study_id!r}")
        if job.status != "done" or job.report is None:
            return error_response(409, "E-API-409", f"report not ready (status: {job.status})")
        return JSONResponse(status_code=200, content={"markdown": job.report})

    return app
