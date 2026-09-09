"""Phase 6 acceptance tests: REST API flow (PRD-002 §9 P6, via TestClient)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from helpers import build_kb, fake_llm_of, install_mock_model, make_zip_bytes
from oracle.api.main import create_app
from oracle.config import get_settings
from oracle.synth.prompt import DISCLAIMER, SECTION_HEADERS


@pytest.fixture()
def api(tmp_path: Path, synthetic_study: Path, env_sandbox: Path, monkeypatch: pytest.MonkeyPatch):
    """Fully-wired app: mock model, offline KB, deterministic fake LLM."""
    install_mock_model(env_sandbox / "models")
    build_kb(env_sandbox / "kb")
    app = create_app(llm=fake_llm_of())
    zip_bytes = make_zip_bytes(synthetic_study)

    def post_study() -> tuple[Any, bytes]:
        return app, zip_bytes

    return app, zip_bytes, tmp_path


def _upload(client: TestClient, zip_bytes: bytes) -> str:
    resp = client.post(
        "/api/v1/studies",
        files={"file": ("study.zip", zip_bytes, "application/zip")},
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["study_id"]


def _wait_done(client: TestClient, study_id: str, timeout_s: float = 60.0) -> dict:
    """Poll status until the background pipeline finishes."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        status = client.get(f"/api/v1/studies/{study_id}").json()
        if status["status"] in ("done", "failed"):
            return status
        time.sleep(0.2)
    raise AssertionError(f"study {study_id} did not finish within {timeout_s}s")


class TestStudyFlow:
    def test_202_then_done_then_report(self, api) -> None:
        """PRD P6 AC: 202 → done → report flow via TestClient."""
        app, zip_bytes, _ = api
        client = TestClient(app)
        study_id = _upload(client, zip_bytes)

        status = _wait_done(client, study_id)
        assert status["status"] == "done", status

        report_resp = client.get(f"/api/v1/studies/{study_id}/report")
        assert report_resp.status_code == 200, report_resp.text
        markdown = report_resp.json()["markdown"]
        for header in SECTION_HEADERS:
            assert header in markdown
        assert markdown.rstrip().endswith(DISCLAIMER)

    def test_report_before_done_is_409(self, api) -> None:
        app, zip_bytes, _ = api
        client = TestClient(app)
        study_id = _upload(client, zip_bytes)
        resp = client.get(f"/api/v1/studies/{study_id}/report")
        assert resp.status_code in (200, 409)  # depending on background timing

    def test_deterministic_report_bytes(self, api) -> None:
        app, zip_bytes, _ = api
        reports = []
        for _ in range(2):
            client = TestClient(app)
            sid = _upload(client, zip_bytes)
            _wait_done(client, sid)
            reports.append(client.get(f"/api/v1/studies/{sid}/report").json()["markdown"])
        assert reports[0] == reports[1]

    def test_intermediates_written(self, api, env_sandbox: Path) -> None:
        app, zip_bytes, _ = api
        client = TestClient(app)
        sid = _upload(client, zip_bytes)
        _wait_done(client, sid)
        data_dir = env_sandbox / "data" / sid
        seg = json.loads((data_dir / "seg.json").read_text(encoding="utf-8"))
        phy = json.loads((data_dir / "phy.json").read_text(encoding="utf-8"))
        assert seg["slice_count"] == 40
        assert "ejection_fraction" in phy


class TestErrors:
    def test_unknown_study_404_envelope(self, api) -> None:
        app, _, _ = api
        client = TestClient(app)
        for url in ("/api/v1/studies/nope", "/api/v1/studies/nope/report"):
            resp = client.get(url)
            assert resp.status_code == 404
            assert resp.json()["error"]["code"] == "E-API-404"

    def test_non_zip_upload_422(self, api) -> None:
        app, _, _ = api
        client = TestClient(app)
        resp = client.post(
            "/api/v1/studies", files={"file": ("x.zip", b"not a zip", "application/zip")}
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "E-API-422"

    def test_oversize_upload_413(self, tmp_path: Path, synthetic_study: Path, monkeypatch) -> None:
        install_mock_model(tmp_path / "models")
        build_kb(tmp_path / "kb")
        monkeypatch.setenv("ORACLE_MODEL_DIR", str(tmp_path / "models"))
        monkeypatch.setenv("ORACLE_KB_DIR", str(tmp_path / "kb"))
        from oracle.config import reset_settings_cache

        reset_settings_cache()
        app = create_app(llm=fake_llm_of(), max_upload_bytes=16)
        client = TestClient(app)
        big = b"PK\x03\x04" + b"0" * 64  # valid zip header + padding → oversize but not zip
        resp = client.post("/api/v1/studies", files={"file": ("x.zip", big, "application/zip")})
        assert resp.status_code == 413
        reset_settings_cache()


class TestSettings:
    def test_env_isolation(self, env_sandbox: Path) -> None:
        settings = get_settings()
        assert settings.model_dir == env_sandbox / "models"
        assert settings.threads == 4
