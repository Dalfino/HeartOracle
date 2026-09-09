"""FFR / wall-stress surrogate v0 (PRD-002 §7 physics.surrogate).

v0 is an honest placeholder: it always returns ``None`` estimates and tags
itself ``placeholder-v0`` so no downstream consumer can mistake it for a
validated hemodynamic model.

Upgrade path (documented, Phase 9+): train a small MLP on synthetic CFD
simulations (Kaggle GPU, §2 budget) over geometry features — LVOT angle,
annulus area, calcification burden — then serve it here behind the same
contract. Until that model exists and validates, nulls are the only
truthful output.
"""

from __future__ import annotations

from typing import Any

from oracle.physics.features import ejection_fraction


def surrogate_outputs(edv_ml: float, esv_ml: float) -> dict[str, Any]:
    """Return the §6 surrogate fields: all nulls in v0."""
    _ = ejection_fraction(edv_ml, esv_ml)  # EF participates in the future model
    return {
        "ffr_estimate": None,
        "ffr_method": "placeholder-v0",
        "wall_stress_mean": None,
    }
