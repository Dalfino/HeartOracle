#!/usr/bin/env python3
"""Convert an ACDC patient's ED/ES frames into an ORACLE-spec 2-phase DICOM zip.

Output zip layout: flat DICOM files, TemporalPositionIdentifier 1=ED / 2=ES,
MR modality, PixelSpacing/SliceThickness/SpacingBetweenSlices set from the
NIfTI header, synthetic PHI tags included so de-identification has work to do.
"""
import sys
import zipfile
from pathlib import Path

import nibabel as nib
import numpy as np
import pydicom
from pydicom.uid import ExplicitVRLittleEndian

DATA = Path("/home/z/oracle-work/data/acdc_testing")
OUT_ZIPS = Path("/home/z/oracle-work/demo-zips")
OUT_ZIPS.mkdir(exist_ok=True)


def convert(pid: int) -> Path:
    pdir = DATA / f"patient{pid}"
    cfg = {}
    for line in (pdir / "Info.cfg").read_text().splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        if k in ("ED", "ES"):
            cfg[k] = int(v.strip())
    ed, es = cfg["ED"], cfg["ES"]

    img_ed = nib.load(str(pdir / f"patient{pid}_frame{ed:02d}.nii.gz"))
    img_es = nib.load(str(pdir / f"patient{pid}_frame{es:02d}.nii.gz"))
    zx, zy, zz = (float(v) for v in img_ed.header.get_zooms()[:3])

    work = Path(f"/tmp/dicom-{pid}")
    work.mkdir(exist_ok=True)
    for f in work.glob("*.dcm"):
        f.unlink()

    n = 0
    for phase_pos, img in ((1, img_ed), (2, img_es)):
        vol = np.asarray(img.dataobj, dtype=np.float32).transpose(2, 0, 1)  # (S,H,W)
        vmax = float(vol.max())
        for s in range(vol.shape[0]):
            slice_i = vol[s]
            px = np.clip(slice_i / vmax * 4000.0, 0, 4095).astype(np.uint16)
            ds = pydicom.Dataset()
            ds.file_meta = pydicom.FileMetaDataset()
            ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"  # MR Image Storage
            ds.file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
            ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            ds.SOPClassUID = ds.file_meta.MediaStorageSOPClassUID
            ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
            # patient / study PHI (synthetic; deidentify must strip these)
            ds.PatientName = f"ACDC^TEST^PATIENT{pid}"
            ds.PatientID = f"ACDC-PID-{pid}-XYZ"
            ds.PatientBirthDate = "19750301"
            ds.PatientSex = "O"
            ds.StudyDate = "20200101"
            ds.StudyTime = "120000"
            ds.InstitutionName = "Sandbox General Hospital"
            ds.ReferringPhysicianName = "DR^REFERENCE"
            ds.AccessionNumber = f"ACC{pid}0000"
            # study / series / image
            ds.Modality = "MR"
            ds.SeriesInstanceUID = pydicom.uid.generate_uid()
            ds.StudyInstanceUID = pydicom.uid.generate_uid()
            ds.InstanceNumber = s + 1
            ds.TemporalPositionIdentifier = phase_pos
            ds.ImagePositionPatient = [0.0, 0.0, s * zz]
            ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
            ds.PixelSpacing = [zy, zx]
            ds.SliceThickness = zz
            ds.SpacingBetweenSlices = zz
            ds.Rows, ds.Columns = px.shape
            ds.SamplesPerPixel = 1
            ds.PhotometricInterpretation = "MONOCHROME2"
            ds.BitsAllocated = 16
            ds.BitsStored = 12
            ds.HighBit = 11
            ds.PixelRepresentation = 0
            ds.WindowCenter = 1200
            ds.WindowWidth = 2400
            ds.RescaleIntercept = 0.0
            ds.RescaleSlope = 1.0
            ds.PixelData = px.tobytes()
            ds.is_little_endian = True
            ds.is_implicit_VR = False
            n += 1
            out_name = f"{pid}_p{phase_pos}_s{s:02d}.dcm"
            pydicom.dcmwrite(
                str(work / out_name), ds, enforce_file_format=True
            )

    zip_path = OUT_ZIPS / f"patient{pid}_demo.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(work.glob("*.dcm")):
            zf.write(f, f.name)
    print(f"{zip_path} ({n} slices)")
    return zip_path


if __name__ == "__main__":
    for pid in [int(x) for x in sys.argv[1:]] or [101]:
        convert(pid)
