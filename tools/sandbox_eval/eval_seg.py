#!/usr/bin/env python3
"""ORACLE segmentation eval on ACDC official testing split — Dice + HD95 + EF.

Resumable: per-frame records append to out/eval_results.jsonl; completed
frames are skipped on re-run. Inference mirrors src/oracle/seg/onnx_infer.py
exactly (bilinear 256, minmax01, argmax, largest-CC at 256, map back >0.5).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import nibabel as nib
import numpy as np
import onnxruntime as ort
from scipy import ndimage

sys.path.insert(0, "/home/z/HeartOracle/src")
from oracle.seg.metrics import dice, hd95, largest_component  # noqa: E402

DATA = Path("/home/z/oracle-work/data/acdc_testing")
MODEL = Path("/home/z/oracle-work/model/oracle-pack/seg_int8.onnx")
OUT = Path("/home/z/oracle-work/out")
OUT.mkdir(exist_ok=True)
RESULTS = OUT / "eval_results.jsonl"
BATCH = 8
STRUCTS = {"LV": 3, "MYO": 2, "RV": 1}


def make_session() -> ort.InferenceSession:
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 2
    opts.inter_op_num_threads = 1
    return ort.InferenceSession(str(MODEL), sess_options=opts, providers=["CPUExecutionProvider"])


def resize(arr: np.ndarray, size: int = 256) -> np.ndarray:
    if arr.shape == (size, size):
        return arr.astype(np.float32)
    out = ndimage.zoom(arr.astype(np.float32), (size / arr.shape[0], size / arr.shape[1]), order=1)
    res = np.zeros((size, size), dtype=np.float32)
    h, w = min(out.shape[0], size), min(out.shape[1], size)
    res[:h, :w] = out[:h, :w]
    return res


def minmax01(arr: np.ndarray) -> np.ndarray:
    lo, hi = float(arr.min()), float(arr.max())
    return (arr - lo) / (hi - lo) if hi > lo else np.zeros_like(arr, dtype=np.float32)


def map_back(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    if mask.shape == shape:
        return mask
    out = ndimage.zoom(
        mask.astype(np.float32),
        (shape[0] / mask.shape[0], shape[1] / mask.shape[1]),
        order=1,
    )
    res = np.zeros(shape, dtype=np.uint8)
    h, w = min(out.shape[0], shape[0]), min(out.shape[1], shape[1])
    res[:h, :w] = (out[:h, :w] > 0.5).astype(np.uint8)
    return res


def volume_ml(mask3d: np.ndarray, pixel_mm2: float, dz: float) -> float:
    return float(mask3d.astype(bool).sum()) * pixel_mm2 * dz / 1000.0


def parse_cfg(pid: int) -> tuple[int, int]:
    ed = es = None
    for line in (DATA / f"patient{pid}" / "Info.cfg").read_text().splitlines():
        if line.startswith("ED:"):
            ed = int(line.split(":")[1].strip())
        elif line.startswith("ES:"):
            es = int(line.split(":")[1].strip())
    return int(ed), int(es)


def load_frame(pid: int, frame: int) -> tuple[np.ndarray, np.ndarray, tuple[float, float, float]]:
    pdir = DATA / f"patient{pid}"
    img = nib.load(str(pdir / f"patient{pid}_frame{frame:02d}.nii.gz"))
    gt = nib.load(str(pdir / f"patient{pid}_frame{frame:02d}_gt.nii.gz"))
    a = np.asarray(img.dataobj, dtype=np.float32).transpose(2, 0, 1)  # (S,H,W)
    g = np.asarray(gt.dataobj, dtype=np.uint8).transpose(2, 0, 1)
    zx, zy, zz = (float(v) for v in img.header.get_zooms()[:3])
    return a, g, (zx, zy, zz)


def infer_phase(sess: ort.InferenceSession, img: np.ndarray) -> np.ndarray:
    """Return labels (S,H,W) at original resolution for one 3D frame."""
    S, H, W = img.shape
    preds = np.zeros((S, H, W), dtype=np.uint8)
    confs: list[float] = []
    for start in range(0, S, BATCH):
        chunk = img[start : start + BATCH]
        x = np.stack([minmax01(resize(sl)) for sl in chunk])[:, None, ...].astype(np.float32)
        logits = sess.run(["logits"], {"input": x})[0]  # (B,4,256,256)
        shifted = logits - logits.max(axis=1, keepdims=True)
        exp = np.exp(shifted)
        probs = exp / exp.sum(axis=1, keepdims=True)
        confs.extend(float(p.max(axis=0).mean()) for p in probs)
        labels = probs.argmax(axis=1).astype(np.uint8)
        for i, lab in enumerate(labels):
            mapped = np.zeros((H, W), dtype=np.uint8)
            for cls in (1, 2, 3):
                b = (lab == cls).astype(np.uint8)
                b = largest_component(b)
                mb = map_back(b, (H, W))
                mapped[mb > 0] = cls
            preds[start + i] = mapped
    return preds, float(np.mean(confs)) if confs else 0.0


def eval_frame(sess: ort.InferenceSession, pid: int, frame: int) -> dict:
    img, gt, (zx, zy, zz) = load_frame(pid, frame)
    t0 = time.perf_counter()
    pred, conf = infer_phase(sess, img)
    dt = time.perf_counter() - t0
    pixel_mm2 = zx * zy

    per_class: dict[str, dict] = {}
    for name, cls in STRUCTS.items():
        g = (gt == cls)
        p = (pred == cls)
        d = float(dice(p, g)) if (g.any() or p.any()) else None
        # per-slice HD95 over slices where both non-empty; count mismatches
        h95s: list[float] = []
        empty_gt_pred = 0
        empty_pred_gt = 0
        for s in range(gt.shape[0]):
            gs, ps = g[s], p[s]
            if not gs.any() and not ps.any():
                continue
            if not gs.any():
                empty_gt_pred += 1
                continue
            if not ps.any():
                empty_pred_gt += 1
                continue
            h95s.append(hd95(ps, gs, (zy, zx)))
        per_class[name] = {
            "dice": d,
            "hd95_mean_mm": float(np.mean(h95s)) if h95s else None,
            "hd95_p95_mm": float(np.percentile(h95s, 95)) if h95s else None,
            "hd95_max_mm": float(np.max(h95s)) if h95s else None,
            "slices_scored": len(h95s),
            "empty_gt_nonempty_pred": empty_gt_pred,
            "empty_pred_nonempty_gt": empty_pred_gt,
            "gt_volume_ml": volume_ml(g, pixel_mm2, zz),
            "pred_volume_ml": volume_ml(p, pixel_mm2, zz),
        }
    return {
        "patient": pid,
        "frame": frame,
        "slices": int(gt.shape[0]),
        "confidence": round(conf, 4),
        "seconds": round(dt, 1),
        "classes": per_class,
    }


def done_frames() -> set[tuple[int, int]]:
    seen: set[tuple[int, int]] = set()
    if RESULTS.exists():
        for line in RESULTS.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                seen.add((r["patient"], r["frame"]))
    return seen


def main(limit_patients: int | None = None) -> None:
    sess = make_session()
    done = done_frames()
    pids = sorted(int(d.name.replace("patient", "")) for d in DATA.iterdir() if d.is_dir())
    if limit_patients:
        pids = pids[:limit_patients]
    total = 0
    for pid in pids:
        ed, es = parse_cfg(pid)
        for fr in (ed, es):
            if (pid, fr) in done:
                continue
            rec = eval_frame(sess, pid, fr)
            with RESULTS.open("a") as fh:
                fh.write(json.dumps(rec) + "\n")
            lv = rec["classes"]["LV"]
            hd = lv["hd95_mean_mm"]
            hd_s = round(hd, 2) if hd is not None else None
            print(
                f"p{pid} f{fr}: LV dice={lv['dice']:.3f} hd95={hd_s} "
                f"conf={rec['confidence']} {rec['seconds']}s", flush=True
            )
            total += 1
    print(f"evaluated {total} new frames")


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(lim)
