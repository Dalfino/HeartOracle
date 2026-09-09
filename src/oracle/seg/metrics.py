"""Segmentation quality metrics (PRD-002 §7 seg.metrics).

dice(a, b): 2|A∩B| / (|A|+|B|); two empty masks agree → 1.0.
hd95(a, b, spacing): symmetric 95th-percentile Hausdorff distance on surface
points, surfaces extracted via XOR with 1-voxel erosion, distances scaled to
mm by *spacing*, computed with distance_transform_edt.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage


def dice(a: np.ndarray, b: np.ndarray) -> float:
    """Sørensen–Dice coefficient between two boolean masks."""
    a_bool, b_bool = np.asarray(a).astype(bool), np.asarray(b).astype(bool)
    denom = int(a_bool.sum()) + int(b_bool.sum())
    if denom == 0:
        return 1.0  # two empty masks agree perfectly
    inter = int(np.logical_and(a_bool, b_bool).sum())
    return 2.0 * inter / denom


def _surface(mask: np.ndarray) -> np.ndarray:
    """Boolean surface (boundary) voxels of a mask: mask XOR eroded(mask)."""
    m = np.asarray(mask).astype(bool)
    if not m.any():
        return np.zeros_like(m)
    eroded = ndimage.binary_erosion(m, structure=ndimage.generate_binary_structure(2, 1))
    return np.logical_xor(m, eroded)


def hd95(a: np.ndarray, b: np.ndarray, spacing: tuple[float, ...] | list[float]) -> float:
    """Symmetric 95th-percentile Hausdorff distance (mm) between two masks."""
    a_bool, b_bool = np.asarray(a).astype(bool), np.asarray(b).astype(bool)
    if not a_bool.any() and not b_bool.any():
        return 0.0
    if not a_bool.any() or not b_bool.any():
        return float("inf")

    surf_a, surf_b = _surface(a_bool), _surface(b_bool)

    def directed(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
        # EDT of the complement of dst surface gives, at every voxel, the
        # distance to the nearest dst-surface voxel.
        dist = ndimage.distance_transform_edt(~dst, sampling=tuple(float(s) for s in spacing))
        return dist[src]

    d_ab, d_ba = directed(surf_a, surf_b), directed(surf_b, surf_a)
    return float(max(np.percentile(d_ab, 95), np.percentile(d_ba, 95)))


def largest_component(mask: np.ndarray) -> np.ndarray:
    """Keep only the largest 4/8-connected component of a boolean mask."""
    m = np.asarray(mask).astype(bool)
    if not m.any():
        return m
    labels, n = ndimage.label(m)
    if n <= 1:
        return m
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    return labels == int(sizes.argmax())
