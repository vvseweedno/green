from dataclasses import dataclass


@dataclass(frozen=True)
class Coverage:
    requested_area_ha: float
    computed_area_ha: float
    coverage_ratio: float
    missing_area_ha: float
    reason: str | None = None


def coverage_result(requested_area_ha: float, computed_area_ha: float, tolerance: float = 1e-6) -> Coverage:
    if requested_area_ha <= 0:
        raise ValueError("requested_area_ha must be positive")
    computed = max(0.0, computed_area_ha)
    ratio = min(1.0, computed / requested_area_ha)
    missing = max(0.0, requested_area_ha - computed)
    reason = None if missing <= tolerance * requested_area_ha else "incomplete_raster_coverage"
    return Coverage(requested_area_ha, computed, ratio, missing, reason)
