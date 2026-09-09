"""DICOM study loading and validation (PRD-002 §7 ingest.dicom_io).

Contract (§6 Study): {"study_token": str(12 hex), "modality": "MR"|"CT",
"n_slices": int, "phases": {"ED": int, "ES": int}, "spacing_mm": [sx, sy],
"thickness_mm": float, "files": int}

Slices are grouped by ``TemporalPositionIdentifier`` (1=ED, 2=ES).
Error matrix (§12): E-ING-001 missing dir · E-ING-002 bad modality ·
E-ING-003 <8 slices/phase · E-ING-004 required tag missing/invalid.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

import numpy as np
import pydicom
from pydicom.dataset import Dataset

from oracle.errors import e_ing_001, e_ing_002, e_ing_003, e_ing_004

VALID_MODALITIES = {"MR", "CT"}
MIN_SLICES_PER_PHASE = 8
PHASE_BY_TEMPORAL_POS = {1: "ED", 2: "ES"}


class Study(TypedDict):
    study_token: str
    modality: str
    n_slices: int
    phases: dict[str, int]
    spacing_mm: list[float]
    thickness_mm: float
    gap_mm: float
    files: int
    study_dir: str


def read_datasets(study_dir: str | Path) -> list[tuple[Path, Dataset]]:
    """Read every readable file under *study_dir*; raise E-ING-001 if none."""
    root = Path(study_dir)
    if not root.is_dir():
        raise e_ing_001("study directory not found", detail=str(root))
    pairs: list[tuple[Path, Dataset]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            pairs.append((path, pydicom.dcmread(path)))
        except Exception:  # noqa: BLE001 - non-DICOM files are skipped
            continue
    if not pairs:
        raise e_ing_001("no readable DICOM files in study directory", detail=str(root))
    return pairs


def _tag(ds: Dataset, name: str) -> Any:
    if name not in ds or ds[name].value in (None, ""):
        raise e_ing_004(f"required DICOM tag missing: {name}")
    return ds[name].value


def load_study(study_dir: str | Path) -> Study:
    """Validate and summarize a DICOM study directory into the §6 Study contract."""
    pairs = read_datasets(study_dir)

    ds0 = pairs[0][1]
    modality = _tag(ds0, "Modality")
    if modality not in VALID_MODALITIES:
        raise e_ing_002(f"unsupported modality {modality!r} (expected MR or CT)")

    phases: dict[str, int] = {"ED": 0, "ES": 0}
    for _, ds in pairs:
        pos = _tag(ds, "TemporalPositionIdentifier")
        phase = PHASE_BY_TEMPORAL_POS.get(int(pos))
        if phase is None:
            raise e_ing_004(
                f"invalid TemporalPositionIdentifier {pos!r} (expected 1=ED, 2=ES)"
            )
        phases[phase] += 1

    for phase, count in phases.items():
        if count < MIN_SLICES_PER_PHASE:
            raise e_ing_003(
                f"phase {phase} has {count} slices (<{MIN_SLICES_PER_PHASE})"
            )

    spacing = [float(v) for v in _tag(ds0, "PixelSpacing")]
    thickness = float(_tag(ds0, "SliceThickness"))
    gap = 0.0
    if "SpacingBetweenSlices" in ds0 and ds0["SpacingBetweenSlices"].value is not None:
        gap = max(0.0, float(ds0["SpacingBetweenSlices"].value) - thickness)

    return Study(
        study_token="",  # filled by deidentify()
        modality=str(modality),
        n_slices=len(pairs),
        phases=phases,
        spacing_mm=spacing,
        thickness_mm=thickness,
        gap_mm=gap,
        files=len(pairs),
        study_dir=str(study_dir),
    )


def sort_slices_by_position(datasets: list[Dataset]) -> list[Dataset]:
    """Sort slice datasets by ImagePositionPatient z (fallback: InstanceNumber)."""
    def z_key(ds: Dataset) -> tuple[float, int]:
        ipp = getattr(ds, "ImagePositionPatient", None)
        if ipp is not None:
            return (float(ipp[2]), int(getattr(ds, "InstanceNumber", 0)))
        return (0.0, int(getattr(ds, "InstanceNumber", 0)))

    return sorted(datasets, key=z_key)


def phase_slices(study_dir: str | Path) -> dict[str, list[Dataset]]:
    """Return {"ED": [ds...], "ES": [ds...]} position-sorted per phase."""
    pairs = read_datasets(study_dir)
    grouped: dict[str, list[Dataset]] = {"ED": [], "ES": []}
    for _, ds in pairs:
        pos = int(_tag(ds, "TemporalPositionIdentifier"))
        grouped[PHASE_BY_TEMPORAL_POS[pos]].append(ds)
    return {phase: sort_slices_by_position(dss) for phase, dss in grouped.items()}


def slice_pixels(ds: Dataset) -> np.ndarray:
    """Return the 2D uint pixel array of a slice."""
    arr = ds.pixel_array
    if arr.ndim != 2:
        raise e_ing_004(f"expected 2D slice, got shape {arr.shape}")
    return arr
