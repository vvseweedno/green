from __future__ import annotations

import numpy as np

DEFAULT_INVALID = frozenset({0, 1, 2, 3, 8, 9, 10, 11})
LOW_CONFIDENCE = frozenset({7})
WATER = 6


def scl_valid_mask(scl, *, allow_low_confidence: bool = True):
    arr = np.asarray(scl)
    valid = ~np.isin(arr, list(DEFAULT_INVALID))
    valid &= arr != WATER
    if not allow_low_confidence:
        valid &= ~np.isin(arr, list(LOW_CONFIDENCE))
    return valid


def scl_quality_summary(scl) -> dict[str, float]:
    arr = np.asarray(scl)
    n = arr.size
    if n == 0:
        return {"valid_fraction": 0.0, "strict_valid_fraction": 0.0, "low_confidence_fraction": 0.0}
    valid = scl_valid_mask(arr, allow_low_confidence=True)
    strict = scl_valid_mask(arr, allow_low_confidence=False)
    low = np.isin(arr, list(LOW_CONFIDENCE))
    return {
        "valid_fraction": float(valid.mean()),
        "strict_valid_fraction": float(strict.mean()),
        "low_confidence_fraction": float(low.mean()),
    }
