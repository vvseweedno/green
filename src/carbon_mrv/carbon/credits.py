from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CreditsResult:
    status: str
    reason: str | None
    R: float | None
    H: float | None
    H_over_R: float | None
    UNC: float | None
    Radj: float | None
    buffer: float | None
    Q: int | None


def _finite(*values: float) -> bool:
    return all(v is not None and math.isfinite(float(v)) for v in values)


def calculate_potential_credits(
    *,
    area_ha: float,
    year_start: int,
    year_end: int,
    Ebase: float | None,
    Eproj: float | None,
    lower: float | None,
    upper: float | None,
    leakage: float = 0.0,
    full_coverage: bool = True,
    baseline_available: bool = True,
) -> CreditsResult:
    """Official hackathon scenario formula. Intermediate values are never rounded."""
    if area_ha <= 0:
        return CreditsResult("unavailable", "non_positive_area", None, None, None, None, None, None, None)
    if year_end <= year_start:
        return CreditsResult("unavailable", "non_positive_interval", None, None, None, None, None, None, None)
    if not full_coverage:
        return CreditsResult("unavailable", "partial_coverage", None, None, None, None, None, None, None)
    if not baseline_available:
        return CreditsResult("unavailable", "baseline_missing", None, None, None, None, None, None, None)
    if not _finite(Ebase, Eproj, lower, upper, leakage):
        return CreditsResult("unavailable", "non_finite_or_missing_input", None, None, None, None, None, None, None)

    Ebase_f, Eproj_f, L, U, LK = map(float, (Ebase, Eproj, lower, upper, leakage))
    H = max(Eproj_f - L, U - Eproj_f)
    if H < 0 or not math.isfinite(H):
        return CreditsResult("unavailable", "invalid_uncertainty", None, None, None, None, None, None, None)
    R = Ebase_f - Eproj_f - LK
    if R <= 0:
        return CreditsResult("available", None, R, H, None, 0.0, R, 0.0, 0)
    ratio = H / R
    if ratio >= 1:
        return CreditsResult("available", None, R, H, ratio, 1.0, 0.0, 0.0, 0)
    unc = min(1.0, max(0.0, ratio - 0.10))
    radj = R * (1.0 - unc)
    buffer = radj * 0.15
    q = math.floor(radj * 0.85)
    return CreditsResult("available", None, R, H, ratio, unc, radj, buffer, q)
