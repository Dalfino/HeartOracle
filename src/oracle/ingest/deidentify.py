"""PHI removal and stable pseudonymization (PRD-002 §7 ingest.deidentify).

Blanked tags: (0010,0010) PatientName · (0010,0020) PatientID ·
(0010,0030) PatientBirthDate · (0008,0080) InstitutionName ·
(0008,0090) ReferringPhysicianName.

study_token = sha256(orig PatientID + StudyInstanceUID)[:12] — deterministic,
derived *before* blanking, never contains PHI itself.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from pydicom.dataset import Dataset

from oracle.ingest.dicom_io import read_datasets

PHI_TAGS: tuple[tuple[int, int], ...] = (
    (0x0010, 0x0010),  # PatientName
    (0x0010, 0x0020),  # PatientID
    (0x0010, 0x0030),  # PatientBirthDate
    (0x0008, 0x0080),  # InstitutionName
    (0x0008, 0x0090),  # ReferringPhysicianName
)


def study_token_for(patient_id: str, study_instance_uid: str) -> str:
    """Deterministic 12-hex study token from original identifiers."""
    raw = f"{patient_id}{study_instance_uid}".encode()
    return hashlib.sha256(raw).hexdigest()[:12]


def _blank_phi(ds: Dataset) -> None:
    for tag in PHI_TAGS:
        if tag in ds:
            ds[tag].value = None


def deidentify(study_dir: str | Path, out_dir: str | Path) -> str:
    """Write a de-identified copy of the study into *out_dir*; return the token."""
    pairs = read_datasets(study_dir)
    ds0 = pairs[0][1]
    patient_id = str(getattr(ds0, "PatientID", "") or "")
    study_uid = str(getattr(ds0, "StudyInstanceUID", "") or "")
    token = study_token_for(patient_id, study_uid)

    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    for i, (src_path, ds) in enumerate(pairs):
        _blank_phi(ds)
        dst = out_root / f"{i:06d}.dcm"
        ds.save_as(dst, enforce_file_format=True)
        del src_path  # originals are never copied verbatim
    return token
