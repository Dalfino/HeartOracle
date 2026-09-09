"""Shared offline fixtures (PRD-002 §0 rule 4: no network, no PHI)."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from make_synthetic_dicom import generate_study  # noqa: E402


@pytest.fixture()
def synthetic_study(tmp_path: Path) -> Iterator[Path]:
    """A generated 2-phase synthetic cardiac MR study."""
    yield generate_study(tmp_path / "synthetic_study")


@pytest.fixture()
def env_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point every ORACLE_* path at a temp sandbox and reset the settings cache."""
    from oracle.config import reset_settings_cache

    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setenv("ORACLE_MODEL_DIR", str(sandbox / "models"))
    monkeypatch.setenv("ORACLE_DATA_DIR", str(sandbox / "data"))
    monkeypatch.setenv("ORACLE_KB_DIR", str(sandbox / "kb"))
    monkeypatch.setenv("ORACLE_THREADS", "4")
    monkeypatch.delenv("ORACLE_ANALYTICS", raising=False)
    monkeypatch.delenv("ORACLE_DEV_LLM", raising=False)
    monkeypatch.delenv("ORACLE_LLM_PATH", raising=False)
    reset_settings_cache()
    yield sandbox
    reset_settings_cache()
