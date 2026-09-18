from __future__ import annotations

import numpy as np


def decode_lossyear(code):
    """Hansen GFC convention: 1 -> 2001, 20 -> 2020, 24 -> 2024."""
    arr = np.asarray(code)
    out = np.zeros_like(arr, dtype=np.int16)
    positive = arr > 0
    out[positive] = 2000 + arr[positive].astype(np.int16)
    return out


def loss_mask_for_transition(lossyear, year_from: int, year_to: int):
    if year_to != year_from + 1:
        raise ValueError("GFC transition mask requires adjacent years")
    return decode_lossyear(lossyear) == year_to
