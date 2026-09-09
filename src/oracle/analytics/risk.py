"""Advisory risk index (PRD-002 §7 analytics.risk).

bio_index(plaque_mm3|None, EF) → 0..10:
    plaque_risk = min(1, (plaque or 0) / 200)
    ef_risk     = clamp((60 − EF) / 60, 0, 1)
    idx         = round(10 · (0.6·plaque_risk + 0.4·ef_risk), 1)
    window      = clamp(int(24 − 1.5·idx), 6, 24)   # months
    flag        = idx ≥ 7.0

Advisory only: this index summarizes deterministic geometry for the local
analytics record; it is not a diagnosis and never triggers treatment logic.
"""

from __future__ import annotations

from datetime import UTC


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def bio_index(plaque_mm3: float | None, ef: float) -> float:
    """Composite 0..10 advisory index from plaque burden and EF."""
    plaque_risk = min(1.0, (plaque_mm3 or 0.0) / 200.0)
    ef_risk = clamp((60.0 - ef) / 60.0, 0.0, 1.0)
    return round(10.0 * (0.6 * plaque_risk + 0.4 * ef_risk), 1)


def risk_window_months(idx: float) -> int:
    """Follow-up window in months, shrinking as the index rises."""
    return int(clamp(float(int(24 - 1.5 * idx)), 6.0, 24.0))


def flag_for(idx: float) -> bool:
    return idx >= 7.0


def make_record(token: str, plaque_mm3: float | None, ef: float) -> dict:
    """Full §6 AnalyticsRecord payload for the vault."""
    idx = bio_index(plaque_mm3, ef)
    from datetime import datetime  # noqa: PLC0415 - cheap, keeps module pure

    return {
        "token": token,
        "bio_index": idx,
        "risk_window_months": risk_window_months(idx),
        "flag": flag_for(idx),
        "created_at": datetime.now(UTC).isoformat(),
    }
