"""Deterministic volumetrics (PRD-002 §7 physics.features).

Simpson slice-summation: V = Σ_i area_i × (thickness + gap)  [mm³ → ml /1000]
EF = (EDV − ESV) / EDV × 100.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def slice_volume_ml(
    mask: np.ndarray, spacing_mm: tuple[float, float] | list[float], increment_mm: float
) -> float:
    """Volume of one slice's binary mask in ml (pixel area × increment)."""
    area_mm2 = (
        float(np.asarray(mask).astype(bool).sum())
        * float(spacing_mm[0])
        * float(spacing_mm[1])
    )
    return area_mm2 * float(increment_mm) / 1000.0


def volumes(
    masks: dict[str, np.ndarray],
    spacing_mm: tuple[float, float] | list[float],
    thickness_mm: float,
    gap_mm: float = 0.0,
) -> tuple[float, float]:
    """Simpson LV volumes from per-phase stacks of binary masks → (EDV, ESV) ml.

    *masks* maps "ED"/"ES" to an (n_slices, H, W) boolean/uint8 array.
    """
    increment = float(thickness_mm) + float(gap_mm)
    out: list[float] = []
    for phase in ("ED", "ES"):
        stack = np.asarray(masks.get(phase, np.zeros((0, 1, 1), dtype=np.uint8)))
        total = 0.0
        for i in range(stack.shape[0]):
            total += slice_volume_ml(stack[i], spacing_mm, increment)
        out.append(total)
    return out[0], out[1]


def ejection_fraction(edv_ml: float, esv_ml: float) -> float:
    """EF percent; a zero (or negative) EDV yields 0.0 by convention."""
    if edv_ml <= 0.0:
        return 0.0
    return (edv_ml - esv_ml) / edv_ml * 100.0


def compute_physics(seg: dict[str, Any], study: dict[str, Any]) -> dict[str, Any]:
    """Build the §6 PhysicsOut contract from a SegOut record + Study record."""
    edv = float(seg["phases"]["ED"]["LV"]["volume_ml"])
    esv = float(seg["phases"]["ES"]["LV"]["volume_ml"])
    return {
        "study_token": seg["study_token"],
        "modality": study.get("modality", "MR"),
        "EDV_ml": round(edv, 3),
        "ESV_ml": round(esv, 3),
        "ejection_fraction": round(ejection_fraction(edv, esv), 2),
        "spacing_mm": list(study.get("spacing_mm", [1.0, 1.0])),
        "thickness_mm": float(study.get("thickness_mm", 1.0)),
        "gap_mm": float(study.get("gap_mm", 0.0)),
        "ffr_estimate": None,
        "ffr_method": "placeholder-v0",
        "wall_stress_mean": None,
    }
