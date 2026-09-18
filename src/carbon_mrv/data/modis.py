from __future__ import annotations

import numpy as np


def qa_bits(qa):
    arr = np.asarray(qa, dtype=np.uint8)
    return {
        "land": (arr & 1) == 1,
        "valid_data": ((arr >> 1) & 1) == 1,
        "shortened_mapping_period": ((arr >> 2) & 1) == 1,
        "relabeled": ((arr >> 3) & 1) == 1,
        "special_condition": (arr >> 5) & 0b111,
    }


def valid_burn_mask(burn_date, qa):
    burn = np.asarray(burn_date)
    bits = qa_bits(qa)
    return (burn > 0) & bits["land"] & bits["valid_data"]


def burn_interval(burn_day: int, uncertainty_days: int, first_day: int, last_day: int) -> tuple[int, int]:
    if burn_day <= 0:
        raise ValueError("burn_day must be positive")
    low = max(1, first_day if first_day > 0 else 1, burn_day - max(0, uncertainty_days))
    high = min(366, last_day if last_day > 0 else 366, burn_day + max(0, uncertainty_days))
    return low, high
