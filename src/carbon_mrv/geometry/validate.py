from __future__ import annotations

from shapely.geometry import shape
from shapely.validation import explain_validity, make_valid

from carbon_mrv.domain.errors import ValidationError
from carbon_mrv.geometry.area import geodesic_area_ha

MAX_AOI_HA = 2_000.0  # 20 km²


def validate_geometry_geojson(geojson: dict, max_area_ha: float = MAX_AOI_HA):
    try:
        geom = shape(geojson)
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(f"Invalid GeoJSON geometry: {exc}") from exc
    if geom.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValidationError("AOI must be Polygon or MultiPolygon")
    if not geom.is_valid:
        repaired = make_valid(geom)
        if repaired.geom_type not in {"Polygon", "MultiPolygon"} or not repaired.is_valid:
            raise ValidationError(f"Invalid AOI geometry: {explain_validity(geom)}")
        geom = repaired
    area_ha = geodesic_area_ha(geom)
    if area_ha <= 0:
        raise ValidationError("AOI area must be positive")
    if area_ha > max_area_ha + 1e-6:
        raise ValidationError(f"AOI area {area_ha:.3f} ha exceeds {max_area_ha:.1f} ha")
    return geom, area_ha


def validate_years(year_start: int, year_end: int) -> None:
    if not (2019 <= year_start <= 2024 and 2019 <= year_end <= 2024):
        raise ValidationError("Supported analysis years are 2019..2024")
    if year_end <= year_start:
        raise ValidationError("year_end must be greater than year_start")
