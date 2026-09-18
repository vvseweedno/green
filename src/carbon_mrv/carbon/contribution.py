from __future__ import annotations

import numpy as np
from affine import Affine

from carbon_mrv.carbon.stock import CF, CO2_PER_C
from carbon_mrv.geometry.area import iter_pixel_overlaps


def event_emission_contribution(
    event_geometry_wgs84,
    agb_start: np.ndarray,
    agb_end: np.ndarray,
    transform: Affine,
) -> dict[str, float]:
    if agb_start.shape != agb_end.shape:
        raise ValueError("start/end CCI grids must match")
    delta_c = 0.0
    event_area = 0.0
    abs_signal = 0.0
    for ov in iter_pixel_overlaps(event_geometry_wgs84, transform, *agb_start.shape):
        b0 = float(agb_start[ov.row, ov.col])
        b1 = float(agb_end[ov.row, ov.col])
        if not np.isfinite(b0) or not np.isfinite(b1):
            continue
        d = (b1 - b0) * CF
        delta_c += ov.area_ha * d
        abs_signal += ov.area_ha * abs(d)
        event_area += ov.area_ha
    return {
        "area_ha": event_area,
        "delta_carbon_t": delta_c,
        "E_event_tco2e": -delta_c * CO2_PER_C,
        "absolute_carbon_change_signal_t": abs_signal,
    }
