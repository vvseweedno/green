from __future__ import annotations

from dataclasses import dataclass

import numpy as np

CF = 0.47
CO2_PER_C = 44.0 / 12.0


@dataclass(frozen=True)
class StockEstimate:
    area_ha: float
    total_carbon_t: float
    mean_carbon_t_ha: float


def agb_to_carbon_t_ha(agb_mg_ha):
    return np.asarray(agb_mg_ha, dtype=float) * CF


def stock_from_weighted_pixels(agb_mg_ha, overlap_area_ha) -> StockEstimate:
    agb = np.asarray(agb_mg_ha, dtype=float)
    area = np.asarray(overlap_area_ha, dtype=float)
    if agb.shape != area.shape:
        raise ValueError("agb and overlap_area_ha must have the same shape")
    valid = np.isfinite(agb) & np.isfinite(area) & (area > 0)
    if not np.any(valid):
        raise ValueError("No valid covered pixels")
    # Zero AGB is valid and intentionally retained.
    a = float(np.sum(area[valid]))
    c = float(np.sum(area[valid] * agb[valid] * CF))
    return StockEstimate(area_ha=a, total_carbon_t=c, mean_carbon_t_ha=c / a)


def stock_difference_emission_tco2e(start: StockEstimate, end: StockEstimate) -> float:
    """E = -(C_t1 - C_t0) * 44/12. Positive E means stock loss."""
    return -(end.total_carbon_t - start.total_carbon_t) * CO2_PER_C


def annualized_emission_intensity(E_tco2e: float, area_ha: float, year_start: int, year_end: int) -> float:
    dt = year_end - year_start
    if area_ha <= 0 or dt <= 0:
        raise ValueError("area_ha and year interval must be positive")
    return E_tco2e / (area_ha * dt)
