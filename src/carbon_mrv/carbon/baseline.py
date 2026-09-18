from __future__ import annotations

from dataclasses import dataclass

from carbon_mrv.carbon.stock import CO2_PER_C


@dataclass(frozen=True)
class BaselineTrajectory:
    parent_aoi_id: str
    cbar_2015_tC_ha: float
    cbar_2019_tC_ha: float

    @property
    def annual_slope_tC_ha(self) -> float:
        return (self.cbar_2019_tC_ha - self.cbar_2015_tC_ha) / 4.0

    def cbar(self, year: int) -> float:
        return max(0.0, self.cbar_2019_tC_ha + self.annual_slope_tC_ha * (year - 2019))

    def emission(self, area_ha: float, year_start: int, year_end: int) -> float:
        if area_ha <= 0 or year_end <= year_start:
            raise ValueError("invalid area/year interval")
        delta_c = area_ha * (self.cbar(year_end) - self.cbar(year_start))
        return -delta_c * CO2_PER_C


def aggregate_baseline(parts: list[tuple[BaselineTrajectory, float]], year_start: int, year_end: int) -> float:
    """Sum disjoint parent-AOI contributions. Caller is responsible for non-overlap."""
    return sum(t.emission(area, year_start, year_end) for t, area in parts)
