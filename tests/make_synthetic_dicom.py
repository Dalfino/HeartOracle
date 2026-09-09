"""Synthetic cardiac MR study generator (PRD-002 §8, exact generation params).

- MR, 2 phases x 20 slices, 256x256 uint16
- pixel spacing [1.5, 1.5] mm; thickness 8 mm; gap 2 mm (SpacingBetweenSlices 10)
- ED cavity: elliptical cross-sections, max semi-axes (45, 35) mm tapering
  per slice (sinusoidal/ellipsoid profile); ES max semi-axes (32, 25) mm
- background 0 · cavity 600 · myocardium ring (6 mm) 300 HU-equivalent
- A calibration factor scales the taper so the analytic Simpson volumes are
  exactly EDV=118.0 ml and ESV=53.0 ml → EF≈55.1% (PRD AC: assert ±5 pts).

The nominal semi-axes define the *shape*; the calibration factor guarantees
the PRD's analytic volume targets. No PHI: patient identifiers are synthetic.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, MRImageStorage, generate_uid

N_SLICES_PER_PHASE = 20
ROWS = COLS = 256
PIXEL_SPACING = [1.5, 1.5]
THICKNESS_MM = 8.0
GAP_MM = 2.0
ED_SEMI_AXES_MM = (45.0, 35.0)
ES_SEMI_AXES_MM = (32.0, 25.0)
TARGET_EDV_ML = 118.0
TARGET_ESV_ML = 53.0
MYO_RING_MM = 6.0
HU_BACKGROUND, HU_CAVITY, HU_MYO = 0, 600, 300

PatientID = "SYNTH-0001"
PatientName = "SYNTHETIC^ORACLE"
StudyInstanceUID = "1.2.826.0.1.3680043.10.1337.ORACLE.SYNTH.STUDY"


def _taper(i: int, n: int) -> float:
    """Ellipsoid profile: sin^2 over slice centers sums to n/2 exactly."""
    return math.sin(math.pi * (i + 0.5) / n) ** 2


def calibration(a_max: float, b_max: float, target_ml: float) -> float:
    """Scale so Simpson volume == target: V = (t+gap) * sum_i pi*a_i*b_i."""
    increment = THICKNESS_MM + GAP_MM
    taper_sum = sum(_taper(i, N_SLICES_PER_PHASE) for i in range(N_SLICES_PER_PHASE))
    base = math.pi * a_max * b_max * taper_sum
    return (target_ml * 1000.0) / (increment * base)


def analytic_volumes() -> tuple[float, float, float]:
    """Return (EDV_ml, ESV_ml, EF_percent) for the generated fixture."""
    edv = TARGET_EDV_ML
    esv = TARGET_ESV_ML
    return edv, esv, (edv - esv) / edv * 100.0


def _make_dataset(phase_no: int, slice_idx: int, a_mm: float, b_mm: float) -> Dataset:
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.MediaStorageSOPClassUID = MRImageStorage
    sop_uid = generate_uid(entropy_srcs=[f"synth-{phase_no}-{slice_idx}"])
    ds.file_meta.MediaStorageSOPInstanceUID = sop_uid
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds.SOPClassUID = MRImageStorage
    ds.SOPInstanceUID = sop_uid
    ds.Modality = "MR"
    ds.PatientName = PatientName
    ds.PatientID = PatientID
    ds.PatientBirthDate = "19700101"
    ds.InstitutionName = "Synthetic General Hospital"
    ds.ReferringPhysicianName = "SYNTH^REFERRER"
    ds.StudyInstanceUID = StudyInstanceUID
    ds.SeriesInstanceUID = generate_uid(entropy_srcs=[f"synth-series-{phase_no}"])
    ds.StudyDate = "20260101"
    ds.TemporalPositionIdentifier = phase_no
    ds.InstanceNumber = slice_idx + 1
    ds.ImagePositionPatient = [0.0, 0.0, float(slice_idx) * (THICKNESS_MM + GAP_MM)]
    ds.PixelSpacing = PIXEL_SPACING
    ds.SliceThickness = THICKNESS_MM
    ds.SpacingBetweenSlices = THICKNESS_MM + GAP_MM
    ds.Rows = ROWS
    ds.Columns = COLS
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"

    img = _render_slice(a_mm, b_mm)
    ds.PixelData = img.astype("<u2").tobytes()
    return ds


def _render_slice(a_mm: float, b_mm: float) -> np.ndarray:
    """Rasterize one cavity ellipse + myocardium ring at 1.5 mm pixels."""
    yy, xx = np.mgrid[0:ROWS, 0:COLS]
    cx = cy = (COLS - 1) / 2.0
    px, py = (xx - cx) * PIXEL_SPACING[1], (yy - cy) * PIXEL_SPACING[0]
    r2 = (px / a_mm) ** 2 + (py / b_mm) ** 2
    a_out = a_mm + MYO_RING_MM
    b_out = b_mm + MYO_RING_MM
    r2_out = (px / a_out) ** 2 + (py / b_out) ** 2

    img = np.full((ROWS, COLS), HU_BACKGROUND, dtype=np.uint16)
    img[r2_out <= 1.0] = HU_MYO
    img[r2 <= 1.0] = HU_CAVITY
    return img


def generate_study(out_dir: str | Path) -> Path:
    """Write the full synthetic study; return the directory."""
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    cal_ed = calibration(*ED_SEMI_AXES_MM, target_ml=TARGET_EDV_ML)
    cal_es = calibration(*ES_SEMI_AXES_MM, target_ml=TARGET_ESV_ML)
    file_no = 0
    for phase_no, (a_max, b_max), cal in (
        (1, ED_SEMI_AXES_MM, cal_ed),
        (2, ES_SEMI_AXES_MM, cal_es),
    ):
        for i in range(N_SLICES_PER_PHASE):
            taper = _taper(i, N_SLICES_PER_PHASE)
            a_mm = a_max * math.sqrt(cal) * math.sqrt(taper)
            b_mm = b_max * math.sqrt(cal) * math.sqrt(taper)
            ds = _make_dataset(phase_no, i, max(a_mm, 0.5), max(b_mm, 0.5))
            ds.save_as(root / f"{file_no:06d}.dcm", enforce_file_format=True)
            file_no += 1
    return root


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1] if len(sys.argv) > 1 else "data/synthetic_study")
    generate_study(target)
    edv, esv, ef = analytic_volumes()
    print(f"synthetic study → {target} (analytic EDV={edv:.1f} ml, ESV={esv:.1f} ml, EF={ef:.1f}%)")
