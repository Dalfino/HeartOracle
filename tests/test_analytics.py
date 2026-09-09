"""Phase 7 acceptance tests: analytics risk + encrypted vault (PRD-002 §9 P7)."""

from __future__ import annotations

import os
import sqlite3
import stat
from pathlib import Path

import pytest

from oracle.analytics.risk import bio_index, flag_for, make_record, risk_window_months
from oracle.analytics.vault import load_key, record, view_records
from oracle.errors import VaultError


class TestBioIndex:
    def test_zero_risk(self) -> None:
        assert bio_index(None, 60.0) == 0.0

    def test_ef_only_formula(self) -> None:
        # ef_risk = (60-55.08)/60 = 0.0820 → idx = 10*0.4*0.0820 = 0.328 → 0.3
        assert bio_index(None, 55.08) == 0.3

    def test_plaque_only_formula(self) -> None:
        # plaque 100 mm³ → risk 0.5 → idx = 10*0.6*0.5 = 3.0
        assert bio_index(100.0, 60.0) == 3.0

    def test_max_risk(self) -> None:
        assert bio_index(200.0, 0.0) == 10.0

    def test_plaque_clamped_at_200(self) -> None:
        assert bio_index(1000.0, 60.0) == bio_index(200.0, 60.0)

    def test_ef_clamped(self) -> None:
        assert bio_index(None, 100.0) == 0.0  # (60-100)/60 clamped to 0
        assert bio_index(None, -10.0) == 4.0  # (60+10)/60 clamped to 1 → 10*0.4

    def test_window_formula(self) -> None:
        assert risk_window_months(0.0) == 24
        assert risk_window_months(10.0) == 9  # int(24-15)

    def test_window_clamped(self) -> None:
        assert risk_window_months(100.0) == 6
        assert risk_window_months(-5.0) == 24

    def test_flag_boundary(self) -> None:
        assert flag_for(7.0) is True
        assert flag_for(6.9) is False


class TestAnalyticsRecord:
    def test_contract_fields(self) -> None:
        rec = make_record("a" * 12, None, 55.08)
        assert set(rec) == {"token", "bio_index", "risk_window_months", "flag", "created_at"}
        assert rec["token"] == "a" * 12
        assert isinstance(rec["bio_index"], float)
        assert isinstance(rec["risk_window_months"], int)
        assert rec["flag"] is False
        assert "T" in rec["created_at"]  # iso timestamp

    def test_high_risk_record_flags(self) -> None:
        rec = make_record("b" * 12, 200.0, 10.0)
        # plaque_risk=1, ef_risk=(60-10)/60≈0.833 → idx=10*(0.6+0.333)=9.3
        assert rec["bio_index"] == 9.3
        assert rec["flag"] is True
        assert rec["risk_window_months"] == int(24 - 1.5 * 9.3)


class TestVault:
    @pytest.fixture()
    def enabled(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        from oracle.config import reset_settings_cache

        monkeypatch.setenv("ORACLE_ANALYTICS", "1")
        monkeypatch.setenv("ORACLE_VAULT_PATH", str(tmp_path / "vault.db"))
        monkeypatch.setenv("ORACLE_VAULT_KEY", str(tmp_path / "vault.key"))
        reset_settings_cache()
        return tmp_path
        # reset happens via env_sandbox-style teardown below

    @pytest.fixture(autouse=True)
    def _teardown(self, monkeypatch: pytest.MonkeyPatch):
        yield
        from oracle.config import reset_settings_cache

        monkeypatch.delenv("ORACLE_ANALYTICS", raising=False)
        reset_settings_cache()

    def test_disabled_is_noop(self, tmp_path: Path) -> None:
        """PRD P7 AC: ORACLE_ANALYTICS=0 → module import-safe no-op."""
        payload = make_record("c" * 12, None, 55.0)
        assert record(payload, vault_path=tmp_path / "none.db", key_path=tmp_path / "k.key") is None
        assert not (tmp_path / "none.db").exists()

    def test_record_and_view_roundtrip(self, enabled: Path) -> None:
        payload = make_record("d" * 12, None, 55.08)
        row_id = record(payload)
        assert row_id is not None
        rows = view_records(key_file=enabled / "vault.key")
        assert len(rows) == 1
        assert rows[0]["token"] == "d" * 12
        assert rows[0]["bio_index"] == payload["bio_index"]
        assert rows[0]["risk_window_months"] == payload["risk_window_months"]
        assert rows[0]["flag"] == payload["flag"]

    def test_ciphertext_differs_from_plaintext(self, enabled: Path) -> None:
        """PRD P7 AC: vault ciphertext ≠ plaintext (assert)."""
        payload = make_record("e" * 12, None, 55.08)
        record(payload)
        conn = sqlite3.connect(enabled / "vault.db")
        blob = conn.execute("SELECT cipher FROM records").fetchone()[0]
        conn.close()
        plaintext = f'"token": "{"e" * 12}"'.encode()
        assert plaintext not in bytes(blob)
        assert b"bio_index" not in bytes(blob)

    def test_key_file_perms_0600(self, enabled: Path) -> None:
        record(make_record("f" * 12, None, 55.08))
        mode = stat.S_IMODE(os.stat(enabled / "vault.key").st_mode)
        assert mode == 0o600

    def test_view_missing_key_raises_e_vlt_001(self, enabled: Path) -> None:
        with pytest.raises(VaultError) as err:
            view_records(key_file=enabled / "no-such.key")
        assert err.value.code == "E-VLT-001"

    def test_wrong_key_raises_e_vlt_002(self, enabled: Path) -> None:
        record(make_record("0" * 12, None, 55.08))
        # overwrite key with a fresh one → decrypt must fail
        from cryptography.fernet import Fernet

        (enabled / "vault.key").write_bytes(Fernet.generate_key())
        with pytest.raises(VaultError) as err:
            view_records(key_file=enabled / "vault.key")
        assert err.value.code == "E-VLT-002"

    def test_load_key_creates_when_allowed(self, tmp_path: Path) -> None:
        key = load_key(tmp_path / "fresh.key", create_if_missing=True)
        assert (tmp_path / "fresh.key").is_file()
        assert load_key(tmp_path / "fresh.key") == key
