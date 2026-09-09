"""Phase 1 acceptance tests: ingest + de-identification (PRD-002 §9 P1)."""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest
from pydicom import dcmread

from make_synthetic_dicom import PatientID, PatientName, StudyInstanceUID
from oracle.errors import IngestError
from oracle.ingest.deidentify import PHI_TAGS, deidentify, study_token_for
from oracle.ingest.dicom_io import load_study

TOKEN_RE = re.compile(r"^[0-9a-f]{12}$")


class TestLoadStudy:
    def test_round_trip_load(self, synthetic_study: Path) -> None:
        study = load_study(synthetic_study)
        assert study["modality"] == "MR"
        assert study["n_slices"] == 40
        assert study["phases"] == {"ED": 20, "ES": 20}
        assert study["spacing_mm"] == [1.5, 1.5]
        assert study["thickness_mm"] == 8.0
        assert study["gap_mm"] == 2.0
        assert study["files"] == 40

    def test_load_under_30s(self, synthetic_study: Path) -> None:
        start = time.perf_counter()
        load_study(synthetic_study)
        assert time.perf_counter() - start < 30.0

    def test_missing_dir_raises_e_ing_001(self, tmp_path: Path) -> None:
        with pytest.raises(IngestError) as err:
            load_study(tmp_path / "does-not-exist")
        assert err.value.code == "E-ING-001"

    def test_bad_modality_raises_e_ing_002(self, synthetic_study: Path) -> None:
        victim = sorted(synthetic_study.glob("*.dcm"))[0]
        ds = dcmread(victim)
        ds.Modality = "DX"
        ds.save_as(victim, enforce_file_format=True)
        with pytest.raises(IngestError) as err:
            load_study(synthetic_study)
        assert err.value.code == "E-ING-002"

    def test_too_few_slices_raises_e_ing_003(self, synthetic_study: Path) -> None:
        for victim in sorted(synthetic_study.glob("*.dcm"))[:15]:
            victim.unlink()
        with pytest.raises(IngestError) as err:
            load_study(synthetic_study)
        assert err.value.code == "E-ING-003"

    def test_missing_temporal_tag_raises_e_ing_004(self, synthetic_study: Path) -> None:
        victim = sorted(synthetic_study.glob("*.dcm"))[0]
        ds = dcmread(victim)
        del ds["TemporalPositionIdentifier"]
        ds.save_as(victim, enforce_file_format=True)
        with pytest.raises(IngestError) as err:
            load_study(synthetic_study)
        assert err.value.code == "E-ING-004"

    def test_invalid_temporal_value_raises_e_ing_004(self, synthetic_study: Path) -> None:
        victim = sorted(synthetic_study.glob("*.dcm"))[0]
        ds = dcmread(victim)
        ds.TemporalPositionIdentifier = 7
        ds.save_as(victim, enforce_file_format=True)
        with pytest.raises(IngestError) as err:
            load_study(synthetic_study)
        assert err.value.code == "E-ING-004"


class TestDeidentify:
    def test_token_is_deterministic_12hex(self, synthetic_study: Path, tmp_path: Path) -> None:
        token_a = deidentify(synthetic_study, tmp_path / "a")
        token_b = deidentify(synthetic_study, tmp_path / "b")
        assert token_a == token_b
        assert TOKEN_RE.match(token_a)
        assert token_a == study_token_for(PatientID, StudyInstanceUID)

    def test_token_varies_with_patient_id(self, synthetic_study: Path) -> None:
        t1 = study_token_for("P1", StudyInstanceUID)
        t2 = study_token_for("P2", StudyInstanceUID)
        assert t1 != t2

    def test_phi_tags_blanked(self, synthetic_study: Path, tmp_path: Path) -> None:
        deidentify(synthetic_study, tmp_path / "anon")
        out_files = sorted((tmp_path / "anon").glob("*.dcm"))
        assert len(out_files) == 40
        for path in out_files:
            ds = dcmread(path)
            for tag in PHI_TAGS:
                if tag in ds:
                    assert ds[tag].value in (None, "")

    def test_no_phi_substrings_in_output_tree(
        self, synthetic_study: Path, tmp_path: Path
    ) -> None:
        out_dir = tmp_path / "anon"
        deidentify(synthetic_study, out_dir)
        secrets = [
            PatientName,
            PatientID,
            "Synthetic General Hospital",
            "SYNTH^REFERRER",
            "19700101",
        ]
        for path in sorted(out_dir.rglob("*")):
            if path.is_file():
                blob = path.read_bytes()
                for secret in secrets:
                    assert secret.encode() not in blob, f"PHI leak {secret!r} in {path.name}"

    def test_no_phi_in_token(self, synthetic_study: Path, tmp_path: Path) -> None:
        token = deidentify(synthetic_study, tmp_path / "anon")
        assert PatientID not in token and PatientName not in token
