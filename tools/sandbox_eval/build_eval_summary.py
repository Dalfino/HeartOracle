#!/usr/bin/env python3
"""Aggregate eval_results.jsonl -> out/eval_summary.json for the dashboard.

Ensemble stats are computed fresh from this session's measurements. The
single-fold reference numbers are carried from the prior session's identical
protocol (same split, same preprocessing) and clearly labeled as recorded.
"""
import json
import statistics
from pathlib import Path

OUT = Path("/home/z/oracle-work/out")
RESULTS = OUT / "eval_results.jsonl"
STRUCTS = ("LV", "MYO", "RV")
GATES = {"LV": 0.90, "MYO": 0.82, "RV": 0.85}

# Prior session, identical protocol (ACDC testing 101-115, minmax01, 256px):
# fold-1 single-model per-frame Dice, recorded in the worklog.
PRIOR_SINGLE = {"LV": 0.8907, "MYO": 0.8251, "RV": 0.7896}
PRIOR_ENSEMBLE = {"LV": 0.8997, "MYO": 0.8473, "RV": 0.8257}
HD95_GATE_MM = 6.0  # PRD §9 P2 HD95(LV) gate


def main() -> None:
    rows = [
    json.loads(line)
    for line in RESULTS.read_text().splitlines()
    if line.strip()
]
    n_frames = len(rows)
    slices_scored = {c: 0 for c in STRUCTS}
    inf_counts = {c: 0 for c in STRUCTS}

    per_frame = {c: [] for c in STRUCTS}
    hd95_means = {c: [] for c in STRUCTS}
    hd95_all = {c: [] for c in STRUCTS}
    total_slices = sum(r.get("slices", 0) for r in rows)
    total_seconds = sum(r["seconds"] for r in rows)
    ms_per_slice = int(total_seconds * 1000 / max(1, total_slices))

    for r in rows:
        for c in STRUCTS:
            d = r["classes"][c]
            if d["dice"] is not None:
                per_frame[c].append(d["dice"])
            # volume-level dice per frame is what we record; per-slice view uses
            # the slice-level hd95 slice count as a proxy for scored slices
            slices_scored[c] += d["slices_scored"]
            inf_counts[c] += d["empty_pred_nonempty_gt"]
            if d["hd95_mean_mm"] is not None:
                hd95_means[c].append(d["hd95_mean_mm"])
            if d["hd95_p95_mm"] is not None:
                hd95_all[c].append(d["hd95_p95_mm"])

    ens_mean = {c: float(statistics.mean(per_frame[c])) for c in STRUCTS}
    ens_median = {c: float(statistics.median(per_frame[c])) for c in STRUCTS}
    ens_std = {
        c: float(statistics.pstdev(per_frame[c])) if len(per_frame[c]) > 1 else 0.0
        for c in STRUCTS
    }

    hd95_mean_mm = {c: float(statistics.mean(hd95_means[c])) for c in STRUCTS}
    hd95_p95_mm = {c: float(statistics.mean(hd95_all[c])) for c in STRUCTS}

    gates = {}
    for c in STRUCTS:
        gates[c] = {
            "single_frame": PRIOR_SINGLE[c],
            "ensemble_frame": round(ens_mean[c], 4),
            "single_slice": None,
            "ensemble_slice": None,
            "gate": GATES[c],
            "single_pass": PRIOR_SINGLE[c] >= GATES[c],
            "ensemble_pass": bool(ens_mean[c] >= GATES[c]),
        }

    # EF comparison per patient: EDV/ESV from predicted vs GT LV blood-pool
    # volumes at each patient's ED/ES frame (Simpson, dz from NIfTI header).
    frame_phase: dict[tuple[int, int], str] = {}
    for r in rows:
        pid = r["patient"]
        cfg_path = Path(f"/home/z/oracle-work/data/acdc_testing/patient{pid}/Info.cfg")
        ed = None
        for line in cfg_path.read_text().splitlines():
            if line.startswith("ED:"):
                ed = int(line.split(":")[1].strip())
        frame_phase[(pid, r["frame"])] = "ED" if r["frame"] == ed else "ES"

    ef_errors: list[float] = []
    ef_records = []
    for r in rows:
        phase = frame_phase.get((r["patient"], r["frame"]))
        if phase is None:
            continue
        lv = r["classes"]["LV"]
        rec = {
            "patient": r["patient"],
            "phase": phase,
            "gt_volume_ml": round(lv["gt_volume_ml"], 1),
            "pred_volume_ml": round(lv["pred_volume_ml"], 1),
        }
        ef_records.append(rec)

    by_patient: dict[int, dict[str, dict[str, float]]] = {}
    for rec in ef_records:
        by_patient.setdefault(rec["patient"], {})[rec["phase"]] = rec
    for _pid, phases in sorted(by_patient.items()):
        if "ED" not in phases or "ES" not in phases:
            continue
        gt_ed, gt_es = phases["ED"]["gt_volume_ml"], phases["ES"]["gt_volume_ml"]
        p_ed, p_es = phases["ED"]["pred_volume_ml"], phases["ES"]["pred_volume_ml"]
        if gt_ed > 0 and p_ed > 0:
            gt_ef = (gt_ed - gt_es) / gt_ed * 100.0
            p_ef = (p_ed - p_es) / p_ed * 100.0
            ef_errors.append(p_ef - gt_ef)

    ef_mae = float(statistics.mean(abs(e) for e in ef_errors)) if ef_errors else None
    ef_bias = float(statistics.mean(ef_errors)) if ef_errors else None
    ef_max = float(max(abs(e) for e in ef_errors)) if ef_errors else None

    summary = {
        "model": "AttentionUNet 5-fold logit-mean ensemble (ONNX INT8, CPU)",
        "n_frames": n_frames,
        "n_slices_scored": slices_scored,
        "infer_ms_per_slice": ms_per_slice,
        "per_frame_mean": {c: round(ens_mean[c], 4) for c in STRUCTS},
        "per_frame_median": {c: round(ens_median[c], 4) for c in STRUCTS},
        "per_frame_std": {c: round(ens_std[c], 4) for c in STRUCTS},
        "hd95_mean_mm": {c: round(hd95_mean_mm[c], 3) for c in STRUCTS},
        "hd95_p95_mm": {c: round(hd95_p95_mm[c], 3) for c in STRUCTS},
        "hd95_gate_mm": HD95_GATE_MM,
        "hd95_lv_pass": bool(hd95_mean_mm["LV"] <= HD95_GATE_MM),
        "empty_pred_counts": inf_counts,
        "ef": {
            "n_patients": len(ef_errors),
            "mae_pp": round(ef_mae, 2) if ef_mae is not None else None,
            "bias_pp": round(ef_bias, 2) if ef_bias is not None else None,
            "max_abs_pp": round(ef_max, 2) if ef_max is not None else None,
            "unit": "percentage points, predicted minus ground truth",
        },
        "frames_with_zero_dice": {
            c: sum(1 for v in per_frame[c] if v == 0.0) for c in STRUCTS
        },
        "gates": gates,
        "single": {
            "model": "AttentionUNet fold-1 (recorded, prior session, identical protocol)",
            "recorded_prior_session": True,
            "per_frame_mean": PRIOR_SINGLE,
            "ensemble_prior": PRIOR_ENSEMBLE,
        },
        "protocol": {
            "split": "ACDC official testing patients 101-115 (30 ED/ES frames)",
            "norm": "minmax01 (B-009)",
            "resize": "256",
            "postprocess": "argmax + largest-CC per class at 256, mapped back >0.5",
            "dice_level": "volume-level (2|∩|/(|A|+|B|) over all slices of the frame)",
            "hd95": "symmetric 95th-percentile surface distance, mm, EDT-based, in-plane spacing",
        },
    }
    (OUT / "eval_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2)[:1200])


if __name__ == "__main__":
    main()
