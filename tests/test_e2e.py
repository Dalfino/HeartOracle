"""Phase 6 acceptance tests: end-to-end pipeline + CLI surface (PRD-002 §9)."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from helpers import (
    TESTS_DIR,
    build_kb,
    compliant_report,
    fake_llm_of,
    install_mock_model,
)
from oracle.errors import OracleError
from oracle.ingest.deidentify import deidentify
from oracle.ingest.dicom_io import load_study
from oracle.physics.features import compute_physics
from oracle.rag.kb_build import HashEmbedder
from oracle.rag.retrieve import retrieve
from oracle.seg.onnx_infer import segment
from oracle.synth.prompt import DISCLAIMER, SECTION_HEADERS
from oracle.synth.report import synthesize_report


def _run_pipeline(tmp_path: Path, synthetic_study: Path, llm) -> tuple[str, dict, dict]:
    token = deidentify(synthetic_study, tmp_path / "anon")
    study = load_study(tmp_path / "anon")
    study["study_token"] = token
    seg = segment(study, tmp_path / "models")
    phy = compute_physics(seg, study)
    chunks = retrieve(
        {
            "modality": phy["modality"],
            "ejection_fraction": phy["ejection_fraction"],
            "abnormal_findings": "annulus 28 mm severe aortic stenosis",
        },
        str(tmp_path / "kb"),
        embedder=HashEmbedder(),
    )
    report, result = synthesize_report(seg, phy, chunks, llm=llm, out_path=tmp_path / "report.md")
    assert result.passed, result.failures
    return report, seg, phy


@pytest.fixture()
def wired_env(tmp_path: Path, synthetic_study: Path) -> Path:
    install_mock_model(tmp_path / "models")
    build_kb(tmp_path / "kb")
    return tmp_path


class TestEndToEnd:
    def test_full_pipeline_under_600s(self, wired_env: Path, synthetic_study: Path) -> None:
        """PRD P6 AC: e2e (with offline stand-ins) completes well under 600 s."""
        start = time.perf_counter()
        report, seg, phy = _run_pipeline(wired_env, synthetic_study, fake_llm_of())
        elapsed = time.perf_counter() - start

        assert elapsed < 600.0
        for header in SECTION_HEADERS:
            assert header in report
        assert report.rstrip().endswith(DISCLAIMER)
        # mock model contract: argmax ≡ MYO everywhere → LV cavity empty → EDV 0
        assert phy["EDV_ml"] == 0.0
        assert phy["ejection_fraction"] == 0.0
        assert seg["confidence"] > 0.9

    def test_e2e_determinism_byte_identical(self, wired_env: Path, synthetic_study: Path) -> None:
        """temp=0 contract: two runs produce byte-identical reports."""
        a, _, _ = _run_pipeline(wired_env, synthetic_study, fake_llm_of())
        b, _, _ = _run_pipeline(wired_env, synthetic_study, fake_llm_of())
        assert a == b

    def test_missing_model_fails_loudly(self, wired_env: Path, synthetic_study: Path) -> None:
        import shutil

        token = deidentify(synthetic_study, wired_env / "anon2")
        study = load_study(wired_env / "anon2")
        study["study_token"] = token
        shutil.rmtree(wired_env / "models")
        with pytest.raises(OracleError) as err:
            segment(study, wired_env / "models")
        assert err.value.code == "E-SEG-001"


class TestCli:
    def test_version_p0_ac(self) -> None:
        """PRD P0 AC: `python -m oracle.cli --version` prints 0.1.0."""
        proc = subprocess.run(
            [sys.executable, "-m", "oracle.cli", "--version"],
            cwd=TESTS_DIR.parent,
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(TESTS_DIR.parent / "src"), "PATH": "/usr/bin:/bin"},
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "0.1.0"

    def test_cli_no_args_exit_nonzero(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "oracle.cli"],
            cwd=TESTS_DIR.parent,
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(TESTS_DIR.parent / "src"), "PATH": "/usr/bin:/bin"},
        )
        assert proc.returncode != 0
        assert "usage" in proc.stderr.lower()

    def test_compliant_builder_available(self) -> None:
        report = compliant_report(
            {"confidence": 1.0},
            {"EDV_ml": 1.0, "ESV_ml": 0.0, "ejection_fraction": 100.0},
            [],
        )
        assert report.endswith(DISCLAIMER)
