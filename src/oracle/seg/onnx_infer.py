"""CPU ONNX segmentation (PRD-002 §7 seg.onnx_infer).

Per slice: bilinear resize → input_size² · normalize (meta ``norm``:
"minmax01" per B-009 finding, else z-score with meta mean/std) · ORT session
with ``intra_op_num_threads = ORACLE_THREADS`` · postprocess: argmax +
largest-connected-component per structure class · confidence = mean of the
per-slice max softmax probability.

SegOut (§6) plus two documented extensions:
- ``phases``: per-phase structure volumes {"ED": {...}, "ES": {...}} — the
  top-level ``structures`` mirrors the ED phase;
- volumes are computed by Simpson slice-summation with spacing/thickness/gap
  taken from the Study record.

Error matrix: E-SEG-001 model/meta missing · E-SEG-002 tensor shape mismatch.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from scipy import ndimage

from oracle.config import get_settings
from oracle.errors import e_seg_001, e_seg_002
from oracle.ingest.dicom_io import Study, phase_slices, slice_pixels
from oracle.seg.metrics import largest_component

STRUCTURES = ("LV", "MYO", "RV")


def load_meta(model_dir: str | Path) -> dict[str, Any]:
    """Read and validate the model sidecar meta.json (§6)."""
    path = Path(model_dir) / "meta.json"
    if not path.is_file():
        raise e_seg_001("meta.json not found in model dir", detail=str(path))
    with path.open(encoding="utf-8") as fh:
        meta = json.load(fh)
    for key in ("input_name", "output_name", "input_size", "classes"):
        if key not in meta:
            raise e_seg_001(f"meta.json missing required key: {key}")
    return meta


def _make_session(model_path: Path) -> ort.InferenceSession:
    if not model_path.is_file():
        raise e_seg_001("ONNX model file not found", detail=str(model_path))
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = get_settings().threads
    opts.inter_op_num_threads = 1
    try:
        return ort.InferenceSession(
            str(model_path), sess_options=opts, providers=["CPUExecutionProvider"]
        )
    except Exception as exc:  # noqa: BLE001
        raise e_seg_001(f"failed to load ONNX model: {exc}") from exc


def _resize_bilinear(arr: np.ndarray, size: int) -> np.ndarray:
    if arr.shape == (size, size):
        return arr.astype(np.float32)
    zoom_y, zoom_x = size / arr.shape[0], size / arr.shape[1]
    out = ndimage.zoom(arr.astype(np.float32), (zoom_y, zoom_x), order=1)
    # zoom rounding guard: pad or crop to exactly (size, size)
    result = np.zeros((size, size), dtype=np.float32)
    h, w = min(out.shape[0], size), min(out.shape[1], size)
    result[:h, :w] = out[:h, :w]
    return result


def _normalize(arr: np.ndarray, meta: dict[str, Any]) -> np.ndarray:
    if meta.get("norm") == "minmax01":
        lo, hi = float(arr.min()), float(arr.max())
        return (arr - lo) / (hi - lo) if hi > lo else np.zeros_like(arr, dtype=np.float32)
    mean, std = float(meta.get("mean", 0.0)), float(meta.get("std", 1.0))
    return (arr - mean) / (std if std != 0.0 else 1.0)


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=0, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=0, keepdims=True)


def _mask_to_original(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    if mask.shape == shape:
        return mask
    zoom = (shape[0] / mask.shape[0], shape[1] / mask.shape[1])
    out = ndimage.zoom(mask.astype(np.float32), zoom, order=1)
    result = np.zeros(shape, dtype=np.uint8)
    h, w = min(out.shape[0], shape[0]), min(out.shape[1], shape[1])
    result[:h, :w] = (out[:h, :w] > 0.5).astype(np.uint8)
    return result


def _volume_ml(mask: np.ndarray, pixel_area_mm2: float, slice_increment_mm: float) -> float:
    area_mm2 = float(mask.astype(bool).sum()) * pixel_area_mm2
    return area_mm2 * slice_increment_mm / 1000.0


def segment(study: Study, model_dir: str | Path) -> dict[str, Any]:
    """Run 2.5D segmentation over both phases of *study*; return the SegOut dict."""
    meta = load_meta(model_dir)
    size = int(meta["input_size"])
    classes: list[str] = list(meta["classes"])
    model_path = Path(model_dir) / "seg_int8.onnx"
    if not model_path.is_file():
        model_path = Path(model_dir) / "seg.onnx"
    session = _make_session(model_path)

    input_shape = session.get_inputs()[0].shape
    dims = [d for d in input_shape[2:] if isinstance(d, int)]
    if dims and dims != [size, size]:
        raise e_seg_002(
            f"model spatial dims {dims} contradict meta input_size {size}"
        )

    start = time.perf_counter()
    pixel_area = float(study["spacing_mm"][0]) * float(study["spacing_mm"][1])
    increment = float(study["thickness_mm"]) + float(study.get("gap_mm", 0.0))

    phase_volumes: dict[str, dict[str, dict[str, float]]] = {}
    confidences: list[float] = []
    masks_payload: dict[str, np.ndarray] = {}
    slice_count = 0

    for phase in ("ED", "ES"):
        phase_volumes[phase] = {}
        per_class_masks: dict[str, list[np.ndarray]] = {s: [] for s in STRUCTURES}
        for ds in phase_slices(study["study_dir"])[phase]:
            raw = slice_pixels(ds)
            x = _normalize(_resize_bilinear(raw, size), meta)[None, None, ...]
            try:
                logits = session.run([meta["output_name"]], {meta["input_name"]: x})[0]
            except Exception as exc:  # noqa: BLE001
                raise e_seg_002(f"session.run failed: {exc}") from exc
            logits = np.squeeze(logits)
            if logits.ndim != 3 or logits.shape[0] != len(classes):
                raise e_seg_002(f"unexpected output shape {logits.shape}")
            probs = _softmax(logits)
            confidences.append(float(probs.max(axis=0).mean()))
            labels = probs.argmax(axis=0)
            for structure in STRUCTURES:
                idx = classes.index(structure)
                binary = (labels == idx).astype(np.uint8)
                binary = largest_component(binary)
                per_class_masks[structure].append(_mask_to_original(binary, raw.shape))
            slice_count += 1

        for structure in STRUCTURES:
            masks = per_class_masks[structure]
            volume = sum(_volume_ml(m, pixel_area, increment) for m in masks)
            phase_volumes[phase][structure] = {"volume_ml": round(volume, 3)}
            masks_payload[f"{phase}/{structure}"] = (
                np.stack(masks) if masks else np.zeros((0,) + (size, size), dtype=np.uint8)
            )

    inference_ms = int((time.perf_counter() - start) * 1000)

    masks_dir = Path(get_settings().data_dir) / study["study_token"]
    masks_dir.mkdir(parents=True, exist_ok=True)
    masks_path = masks_dir / "masks.npz"
    np.savez_compressed(masks_path, **masks_payload)

    return {
        "study_token": study["study_token"],
        "model_id": str(meta.get("source", model_path.name)),
        "quant": str(meta.get("quant", "fp32")),
        "confidence": round(float(np.mean(confidences)) if confidences else 0.0, 6),
        "structures": phase_volumes["ED"],
        "phases": phase_volumes,
        "masks_path": str(masks_path),
        "slice_count": slice_count,
        "inference_ms": inference_ms,
    }
