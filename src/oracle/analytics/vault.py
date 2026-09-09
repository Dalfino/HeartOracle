"""Encrypted local analytics vault (PRD-002 §7 analytics.vault).

Fernet key file (mode 0600, enforced) + SQLite table
``records(id INTEGER PK, token TEXT, cipher BLOB, created_at TEXT)``.
The whole module is gated by ``ORACLE_ANALYTICS``: when disabled it is an
import-safe no-op — nothing is written, no key is required (§9 P7).

Error matrix: E-VLT-001 key file missing · E-VLT-002 decrypt failure.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from oracle.config import get_settings
from oracle.errors import e_vlt_001, e_vlt_002

_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY,
    token TEXT NOT NULL,
    cipher BLOB NOT NULL,
    created_at TEXT NOT NULL
)
"""


def _fernet():
    from cryptography.fernet import Fernet  # noqa: PLC0415 - lazy import

    return Fernet


def _enforce_0600(path: Path) -> None:
    os.chmod(path, 0o600)


def load_key(key_path: str | Path, *, create_if_missing: bool = False) -> bytes:
    """Read the Fernet key; optionally create one (0600) on first use."""
    path = Path(key_path)
    if not path.is_file():
        if not create_if_missing:
            raise e_vlt_001("vault key file not found", detail=str(path))
        Fernet = _fernet()
        key = Fernet.generate_key()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(key)
        _enforce_0600(path)
        return key
    _enforce_0600(path)
    return path.read_bytes()


def _connect(vault_path: Path) -> sqlite3.Connection:
    vault_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(vault_path)
    conn.execute(_SCHEMA)
    return conn


def record(
    payload: dict[str, Any],
    *,
    vault_path: str | Path | None = None,
    key_path: str | Path | None = None,
) -> int | None:
    """Encrypt + store one AnalyticsRecord; no-op when ORACLE_ANALYTICS=0.

    Returns the new row id, or None when analytics is disabled.
    """
    settings = get_settings()
    if not settings.analytics:
        return None

    Fernet = _fernet()
    key = load_key(key_path or settings.vault_key or "vault.key", create_if_missing=True)
    cipher = Fernet(key).encrypt(json.dumps(payload, sort_keys=True).encode("utf-8"))
    vault = Path(vault_path or settings.vault_path)
    conn = _connect(vault)
    try:
        cur = conn.execute(
            "INSERT INTO records (token, cipher, created_at) VALUES (?, ?, ?)",
            (
                str(payload.get("token", "")),
                cipher,
                payload.get("created_at") or datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def view_records(
    *,
    key_file: str | Path,
    limit: int = 10,
    vault_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Decrypt and list the most recent records (CLI `oracle vault view`)."""
    settings = get_settings()
    key_file = Path(key_file)
    if not key_file.is_file():
        raise e_vlt_001("vault key file not found", detail=str(key_file))

    Fernet = _fernet()
    key = load_key(key_file)
    fernet = Fernet(key)
    vault = Path(vault_path or settings.vault_path)
    if not vault.is_file():
        return []

    out: list[dict[str, Any]] = []
    conn = sqlite3.connect(vault)
    try:
        rows = conn.execute(
            "SELECT token, cipher, created_at FROM records ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    finally:
        conn.close()

    for token, cipher, created_at in rows:
        try:
            payload = json.loads(fernet.decrypt(bytes(cipher)).decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - any decrypt/parse problem
            raise e_vlt_002(f"cannot decrypt record for token {token!r}: {exc}") from exc
        out.append({"token": token, "created_at": created_at, **payload})
    return out
