"""ORACLE command line interface (PRD-002 §10).

Commands:
  oracle --version
  oracle ingest   --input DIR --out study.json
  oracle segment  --study study.json --out seg.json
  oracle physics  --seg seg.json --out phy.json
  oracle kb build --guidelines DIR
  oracle report   --seg seg.json --phy phy.json --out report.md
  oracle bench    --input DIR --runs 3 --out bench.json
  oracle serve    --port 8000        # FastAPI
  oracle ui       --port 7860        # Gradio
  oracle vault view --key-file PATH --limit 10      (added in Phase 7)

Exit codes: 0 ok · 2 ingest/validation · 3 model/seg · 4 rag · 5 synth/audit · 6 vault.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from oracle import __version__
from oracle.config import get_settings
from oracle.errors import OracleError
from oracle.logging_util import get_logger, log_event

logger = get_logger("cli")


def _json_read(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _json_write(path: str | Path, payload: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def default_embedder() -> Any:
    """Shared embedder selection (fastembed when installed, offline fallback otherwise)."""
    from oracle.rag.kb_build import default_embedder  # noqa: PLC0415

    return default_embedder()


def build_findings(phy: dict[str, Any]) -> dict[str, Any]:
    ef = float(phy["ejection_fraction"])
    return {
        "modality": phy.get("modality", "MR"),
        "ejection_fraction": ef,
        "abnormal_findings": (
            "reduced ejection fraction" if ef < 40.0 else "preserved ejection fraction"
        ),
    }


# ---------------------------------------------------------------- commands


def cmd_ingest(args: argparse.Namespace) -> int:
    from oracle.ingest.deidentify import deidentify
    from oracle.ingest.dicom_io import load_study

    settings = get_settings()
    t0 = time.perf_counter()
    study = load_study(args.input)
    token = deidentify(args.input, Path(settings.data_dir) / "ingest-tmp")
    # move de-identified tree to its token-keyed home
    final_dir = Path(settings.data_dir) / token
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    if final_dir.exists():
        import shutil

        shutil.rmtree(final_dir)
    (Path(settings.data_dir) / "ingest-tmp").rename(final_dir)
    study["study_token"] = token
    study["study_dir"] = str(final_dir)
    _json_write(args.out, study)
    log_event(
        logger, "ingest_done", study_token=token, duration_ms=(time.perf_counter() - t0) * 1000
    )
    print(f"study {token} → {args.out}")
    return 0


def cmd_segment(args: argparse.Namespace) -> int:
    from oracle.seg.onnx_infer import segment

    t0 = time.perf_counter()
    study = _json_read(args.study)
    seg = segment(study, get_settings().model_dir)
    _json_write(args.out, seg)
    log_event(
        logger, "segment_done", study_token=seg["study_token"],
        duration_ms=(time.perf_counter() - t0) * 1000,
    )
    print(f"segmentation {seg['model_id']} confidence={seg['confidence']:.3f} → {args.out}")
    return 0


def cmd_physics(args: argparse.Namespace) -> int:
    from oracle.physics.features import compute_physics

    t0 = time.perf_counter()
    seg = _json_read(args.seg)
    phy = compute_physics(seg)
    _json_write(args.out, phy)
    log_event(logger, "physics_done", duration_ms=(time.perf_counter() - t0) * 1000)
    print(
        f"EDV {phy['EDV_ml']:.1f} ml · ESV {phy['ESV_ml']:.1f} ml · "
        f"EF {phy['ejection_fraction']:.1f} % → {args.out}"
    )
    return 0


def cmd_kb_build(args: argparse.Namespace) -> int:
    from oracle.rag.kb_build import build

    t0 = time.perf_counter()
    n = build(args.guidelines, str(get_settings().kb_dir), embedder=default_embedder())
    log_event(logger, "kb_build_done", duration_ms=(time.perf_counter() - t0) * 1000)
    print(f"indexed {n} chunks → {get_settings().kb_dir}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from oracle.rag.retrieve import retrieve
    from oracle.synth.report import synthesize_report

    t0 = time.perf_counter()
    seg = _json_read(args.seg)
    phy = _json_read(args.phy)
    chunks = retrieve(build_findings(phy), str(get_settings().kb_dir), embedder=default_embedder())
    report, result = synthesize_report(seg, phy, chunks, out_path=args.out)
    log_event(
        logger, "report_done", study_token=seg.get("study_token"),
        duration_ms=(time.perf_counter() - t0) * 1000,
        audit_passed=result.passed,
    )
    print(f"report (audit {'PASSED' if result.passed else 'FAILED'}) → {args.out}")
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    from oracle.ingest.deidentify import deidentify
    from oracle.ingest.dicom_io import load_study
    from oracle.physics.features import compute_physics
    from oracle.seg.onnx_infer import segment

    runs: dict[str, list[float]] = {"ingest_ms": [], "segment_ms": [], "physics_ms": []}
    bench_dir = Path(get_settings().data_dir) / "bench"
    for _ in range(max(1, args.runs)):
        t0 = time.perf_counter()
        study = load_study(args.input)
        token = deidentify(args.input, bench_dir)
        runs["ingest_ms"].append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        study["study_token"] = token
        seg = segment(study, get_settings().model_dir)
        runs["segment_ms"].append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        phy = compute_physics(seg, study)
        runs["physics_ms"].append((time.perf_counter() - t0) * 1000)

    bench = {
        "runs": args.runs,
        "median_ms": {k: round(statistics.median(v), 1) for k, v in runs.items()},
        "timings_ms": {k: [round(x, 1) for x in v] for k, v in runs.items()},
        "last_ejection_fraction": phy["ejection_fraction"],
        "machine": {"threads": get_settings().threads, "note": "measured with time.perf_counter"},
    }
    _json_write(args.out, bench)
    print(f"bench (median of {args.runs}) → {args.out}: {bench['median_ms']}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:  # pragma: no cover - long-running
    import uvicorn

    from oracle.api.main import create_app

    uvicorn.run(create_app(), host="0.0.0.0", port=args.port)
    return 0


def cmd_ui(args: argparse.Namespace) -> int:  # pragma: no cover - long-running
    from oracle.ui.gradio_app import launch

    launch(port=args.port)
    return 0


def cmd_vault_view(args: argparse.Namespace) -> int:
    from oracle.analytics.vault import view_records

    records = view_records(key_file=args.key_file, limit=args.limit)
    for rec in records:
        print(json.dumps(rec, sort_keys=True))
    print(f"{len(records)} record(s)")
    return 0


# ---------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oracle", description="ORACLE cardiac pipeline")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ingest", help="parse + de-identify a DICOM study")
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("segment", help="ONNX segmentation")
    p.add_argument("--study", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_segment)

    p = sub.add_parser("physics", help="Simpson EDV/ESV/EF")
    p.add_argument("--seg", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_physics)

    p = sub.add_parser("kb", help="guideline knowledge base")
    kb_sub = p.add_subparsers(dest="kb_command", required=True)
    kb_build_p = kb_sub.add_parser("build", help="index guidelines")
    kb_build_p.add_argument("--guidelines", required=True)
    kb_build_p.set_defaults(func=cmd_kb_build)

    p = sub.add_parser("report", help="cited report + audit gate")
    p.add_argument("--seg", required=True)
    p.add_argument("--phy", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("bench", help="timing benchmark")
    p.add_argument("--input", required=True)
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_bench)

    p = sub.add_parser("serve", help="FastAPI server")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("ui", help="Gradio UI")
    p.add_argument("--port", type=int, default=7860)
    p.set_defaults(func=cmd_ui)

    p = sub.add_parser("vault", help="analytics vault")
    vault_sub = p.add_subparsers(dest="vault_command", required=True)
    vault_view = vault_sub.add_parser("view", help="decrypt + list records")
    vault_view.add_argument("--key-file", required=True)
    vault_view.add_argument("--limit", type=int, default=10)
    vault_view.set_defaults(func=cmd_vault_view)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except OracleError as exc:
        log_event(logger, "command_failed", level=40, code=exc.code, message=exc.message)
        print(f"error {exc.code}: {exc.message}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:  # pragma: no cover
        return 130


if __name__ == "__main__":
    sys.exit(main())
