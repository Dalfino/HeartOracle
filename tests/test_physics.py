"""Phase 3 acceptance tests: Simpson volumetrics (PRD-002 §9 P3)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from make_synthetic_dicom import HU_CAVITY, analytic_volumes
from oracle.ingest.dicom_io import load_study, phase_slices, slice_pixels
from oracle.physics.features import (
    compute_physics,
    ejection_fraction,
    slice_volume_ml,
    volumes,
)
from oracle.physics.surrogate import surrogate_outputs


def cavity_masks_from_pixels(study_dir: Path, phase: str) -> np.ndarray:
    """Binary LV-cavity masks by thresholding the synthetic fixture (HU 600)."""
    return np.stack(
        [(slice_pixels(ds) >= HU_CAVITY).astype(np.uint8) for ds in phase_slices(study_dir)[phase]]
    )


class TestSimpsonVolumes:
    def test_analytic_fixture_volumes(self, synthetic_study: Path) -> None:
        """Cavity masks thresholded from fixture pixels reproduce EDV≈118, ESV≈53."""
        masks = {
            "ED": cavity_masks_from_pixels(synthetic_study, "ED"),
            "ES": cavity_masks_from_pixels(synthetic_study, "ES"),
        }
        edv, esv = volumes(masks, spacing_mm=[1.5, 1.5], thickness_mm=8.0, gap_mm=2.0)
        assert edv == pytest.approx(118.0, rel=0.02)
        assert esv == pytest.approx(53.0, rel=0.02)

    def test_ef_within_5_points_of_analytic(self, synthetic_study: Path) -> None:
        """PRD P3 AC: EF error ≤ 5 pts vs the analytic fixture (55.1%)."""
        masks = {
            "ED": cavity_masks_from_pixels(synthetic_study, "ED"),
            "ES": cavity_masks_from_pixels(synthetic_study, "ES"),
        }
        edv, esv = volumes(masks, spacing_mm=[1.5, 1.5], thickness_mm=8.0, gap_mm=2.0)
        ef = ejection_fraction(edv, esv)
        _, _, analytic_ef = analytic_volumes()
        assert abs(ef - analytic_ef) <= 5.0

    def test_single_slice_volume(self) -> None:
        mask = np.ones((10, 10), np.uint8)  # 100 px × 2.25 mm² × 10 mm = 2250 mm³ = 2.25 ml
        assert slice_volume_ml(mask, (1.5, 1.5), 10.0) == pytest.approx(2.25)

    def test_empty_masks_give_zero(self) -> None:
        masks = {"ED": np.zeros((3, 8, 8), np.uint8), "ES": np.zeros((3, 8, 8), np.uint8)}
        edv, esv = volumes(masks, (1.0, 1.0), 5.0)
        assert edv == 0.0 and esv == 0.0

    def test_missing_phase_defaults_zero(self) -> None:
        masks = {"ED": np.ones((2, 8, 8), np.uint8)}
        edv, esv = volumes(masks, (1.0, 1.0), 5.0)
        assert edv > 0.0 and esv == 0.0


class TestEjectionFraction:
    def test_formula(self) -> None:
        assert ejection_fraction(118.0, 53.0) == pytest.approx(55.08, abs=0.1)

    def test_zero_edv_guard(self) -> None:
        assert ejection_fraction(0.0, 0.0) == 0.0

    def test_negative_edv_guard(self) -> None:
        assert ejection_fraction(-5.0, 0.0) == 0.0

    def test_ef_normal_range(self) -> None:
        assert 0.0 <= ejection_fraction(100.0, 20.0) <= 100.0


class TestPhysicsContract:
    def _seg_record(self, synthetic_study: Path) -> dict:
        masks = {
            "ED": cavity_masks_from_pixels(synthetic_study, "ED"),
            "ES": cavity_masks_from_pixels(synthetic_study, "ES"),
        }
        edv, esv = volumes(masks, [1.5, 1.5], 8.0, 2.0)
        return {
            "study_token": "a" * 12,
            "phases": {
                "ED": {"LV": {"volume_ml": edv}},
                "ES": {"LV": {"volume_ml": esv}},
            },
        }, masks

    def test_contract_fields(self, synthetic_study: Path) -> None:
        seg, _ = self._seg_record(synthetic_study)
        study = load_study(synthetic_study)
        phy = compute_physics(seg, study)
        assert set(phy) >= {
            "study_token", "EDV_ml", "ESV_ml", "ejection_fraction",
            "ffr_estimate", "ffr_method", "wall_stress_mean",
        }
        assert phy["ffr_estimate"] is None
        assert phy["ffr_method"] == "placeholder-v0"
        assert phy["wall_stress_mean"] is None

    def test_determinism_hash_equal_json(self, synthetic_study: Path) -> None:
        """PRD P3 AC: identical outputs across 2 runs (hash-equal JSON)."""
        seg, _ = self._seg_record(synthetic_study)
        study = load_study(synthetic_study)
        blobs = [json.dumps(compute_physics(seg, study), sort_keys=True) for _ in range(2)]
        assert hashlib.sha256(blobs[0].encode()).hexdigest() == hashlib.sha256(
            blobs[1].encode()
        ).hexdigest()

    def test_surrogate_v0_nulls(self) -> None:
        out = surrogate_outputs(118.0, 53.0)
        assert out == {
            "ffr_estimate": None,
            "ffr_method": "placeholder-v0",
            "wall_stress_mean": None,
        }

    def test_surrogate_never_raises_on_degenerate_input(self) -> None:
        assert surrogate_outputs(0.0, 0.0)["ffr_method"] == "placeholder-v0"
