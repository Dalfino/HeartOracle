"""Phase 2 acceptance tests: segmentation + metrics (PRD-002 §9 P2)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from make_mock_onnx import BIAS, INPUT_SIZE, mock_meta
from oracle.errors import SegError
from oracle.ingest.deidentify import deidentify
from oracle.ingest.dicom_io import load_study
from oracle.seg.metrics import dice, hd95, largest_component
from oracle.seg.onnx_infer import segment


@pytest.fixture()
def mock_model_dir(tmp_path: Path) -> Path:
    """Model dir holding the committed tiny_seg.onnx + its meta."""
    src = Path(__file__).resolve().parent / "fixtures"
    dst = tmp_path / "models"
    dst.mkdir()
    shutil.copy(src / "tiny_seg.onnx", dst / "seg.onnx")
    (dst / "meta.json").write_text(json.dumps(mock_meta()), encoding="utf-8")
    return dst


@pytest.fixture()
def anon_study(tmp_path: Path, synthetic_study: Path) -> tuple[dict, Path]:
    """De-identified Study record ready for segmentation."""
    token = deidentify(synthetic_study, tmp_path / "anon")
    study = load_study(tmp_path / "anon")
    study["study_token"] = token
    return study, tmp_path


class TestMetrics:
    def test_dice_identical_masks(self) -> None:
        m = np.zeros((64, 64), np.uint8)
        m[16:48, 16:48] = 1
        assert dice(m, m) == 1.0

    def test_dice_disjoint_masks(self) -> None:
        a = np.zeros((64, 64), np.uint8)
        b = np.zeros((64, 64), np.uint8)
        a[0:32, :] = 1
        b[32:64, :] = 1
        assert dice(a, b) == 0.0

    def test_dice_half_overlap(self) -> None:
        a = np.zeros((64, 64), np.uint8)
        b = np.zeros((64, 64), np.uint8)
        a[0:32, 0:32] = 1  # 1024 px
        b[0:32, 16:48] = 1  # 1024 px, overlap 512
        assert dice(a, b) == pytest.approx(2 * 512 / 2048)

    def test_dice_two_empty_masks_agree(self) -> None:
        assert dice(np.zeros((8, 8)), np.zeros((8, 8))) == 1.0

    def test_hd95_identical_is_zero(self) -> None:
        m = np.zeros((64, 64), np.uint8)
        m[16:48, 16:48] = 1
        assert hd95(m, m, spacing=(1.5, 1.5)) == pytest.approx(0.0)

    def test_hd95_equals_known_shift(self) -> None:
        a = np.zeros((128, 128), np.uint8)
        b = np.zeros((128, 128), np.uint8)
        a[32:96, 32:96] = 1
        b[32:96, 32 + 10 : 96 + 10] = 1  # shifted 10 px × 1 mm
        assert hd95(a, b, spacing=(1.0, 1.0)) == pytest.approx(10.0, abs=1.0)

    def test_hd95_scales_with_spacing(self) -> None:
        a = np.zeros((128, 128), np.uint8)
        b = np.zeros((128, 128), np.uint8)
        a[32:96, 32:96] = 1
        b[32:96, 42:106] = 1
        assert hd95(a, b, spacing=(2.0, 2.0)) == pytest.approx(20.0, abs=2.0)

    def test_largest_component_removes_satellites(self) -> None:
        m = np.zeros((64, 64), np.uint8)
        m[8:40, 8:40] = 1  # big blob
        m[50:52, 50:52] = 1  # satellite
        kept = largest_component(m)
        assert kept[50:52, 50:52].sum() == 0
        assert kept.sum() == m[8:40, 8:40].sum()


class TestSegment:
    def test_mock_onnx_argmax_is_class1_everywhere(self) -> None:
        import onnxruntime as ort

        sess = ort.InferenceSession(
            str(Path(__file__).resolve().parent / "fixtures" / "tiny_seg.onnx"),
            providers=["CPUExecutionProvider"],
        )
        x = np.random.default_rng(0).random((1, 1, INPUT_SIZE, INPUT_SIZE), dtype=np.float32)
        out = sess.run(["output"], {"input": x})[0]
        assert out.shape == (1, 4, INPUT_SIZE, INPUT_SIZE)
        assert (out.argmax(axis=1) == 1).all()

    def test_mock_bias_layout(self) -> None:
        assert BIAS == [0.0, 10.0, 0.0, 0.0]

    def test_segment_contract(self, mock_model_dir: Path, anon_study: tuple) -> None:
        study, tmp_path = anon_study
        seg = segment(study, mock_model_dir)
        assert set(seg) >= {
            "study_token", "model_id", "quant", "confidence", "structures",
            "masks_path", "slice_count", "inference_ms",
        }
        assert seg["study_token"] == study["study_token"]
        assert seg["slice_count"] == 40
        assert isinstance(seg["inference_ms"], int)
        assert 0.0 <= seg["confidence"] <= 1.0
        for structure in ("LV", "MYO", "RV"):
            assert "volume_ml" in seg["structures"][structure]
            assert "volume_ml" in seg["phases"]["ES"][structure]

    def test_segment_dice_myo_is_one(self, mock_model_dir: Path, anon_study: tuple) -> None:
        """PRD P2 unit AC: mock ONNX dice(MYO) = 1.00 ± 0.00 vs all-MYO labels."""
        study, _ = anon_study
        seg = segment(study, mock_model_dir)
        masks = np.load(seg["masks_path"])
        all_myo = np.ones((INPUT_SIZE, INPUT_SIZE), np.uint8)
        assert dice(masks["ED/MYO"][0], all_myo) == pytest.approx(1.0)
        assert dice(masks["ES/MYO"][-1], all_myo) == pytest.approx(1.0)

    def test_segment_confidence_matches_softmax_of_bias(
        self, mock_model_dir: Path, anon_study: tuple
    ) -> None:
        study, _ = anon_study
        seg = segment(study, mock_model_dir)
        expected = np.e**10 / (np.e**10 + 3.0)  # softmax max of [0,10,0,0]
        assert seg["confidence"] == pytest.approx(expected, abs=1e-3)

    def test_segment_deterministic(self, mock_model_dir: Path, anon_study: tuple) -> None:
        study, _ = anon_study
        a = segment(study, mock_model_dir)
        b = segment(study, mock_model_dir)
        assert a["structures"] == b["structures"]
        assert a["phases"] == b["phases"]
        assert a["confidence"] == b["confidence"]

    def test_masks_npz_written(self, mock_model_dir: Path, anon_study: tuple) -> None:
        study, _ = anon_study
        seg = segment(study, mock_model_dir)
        masks = np.load(seg["masks_path"])
        assert masks["ED/LV"].shape[0] == 20
        assert masks["ED/MYO"].shape[0] == 20
        assert masks["ES/RV"].shape[0] == 20

    def test_missing_model_raises_e_seg_001(self, anon_study: tuple, tmp_path: Path) -> None:
        study, _ = anon_study
        empty = tmp_path / "empty-models"
        empty.mkdir()
        with pytest.raises(SegError) as err:
            segment(study, empty)
        assert err.value.code == "E-SEG-001"

    def test_shape_mismatch_raises_e_seg_002(
        self, mock_model_dir: Path, anon_study: tuple
    ) -> None:
        study, _ = anon_study
        bad_meta = mock_meta()
        bad_meta["input_size"] = 128  # contradicts the 256² mock model
        (mock_model_dir / "meta.json").write_text(json.dumps(bad_meta), encoding="utf-8")
        with pytest.raises(SegError) as err:
            segment(study, mock_model_dir)
        assert err.value.code == "E-SEG-002"
