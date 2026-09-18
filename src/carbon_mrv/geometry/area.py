from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
from affine import Affine
from pyproj import Geod
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

WGS84_GEOD = Geod(ellps="WGS84")


def geodesic_area_m2(geometry: BaseGeometry) -> float:
    """Absolute WGS84 geodesic area for Polygon/MultiPolygon/collections."""
    if geometry.is_empty:
        return 0.0
    if isinstance(geometry, Polygon):
        area, _ = WGS84_GEOD.geometry_area_perimeter(geometry)
        return abs(float(area))
    if isinstance(geometry, MultiPolygon):
        return sum(geodesic_area_m2(g) for g in geometry.geoms)
    if isinstance(geometry, GeometryCollection):
        return sum(geodesic_area_m2(g) for g in geometry.geoms)
    return 0.0


def geodesic_area_ha(geometry: BaseGeometry) -> float:
    return geodesic_area_m2(geometry) / 10_000.0


@dataclass(frozen=True)
class PixelOverlap:
    row: int
    col: int
    area_ha: float


def pixel_polygon(transform: Affine, row: int, col: int) -> Polygon:
    """Create pixel footprint. North-up and rotated transforms are both supported."""
    p0 = transform * (col, row)
    p1 = transform * (col + 1, row)
    p2 = transform * (col + 1, row + 1)
    p3 = transform * (col, row + 1)
    return Polygon([p0, p1, p2, p3, p0])


def iter_pixel_overlaps(
    geometry_wgs84: BaseGeometry,
    transform: Affine,
    height: int,
    width: int,
) -> Iterator[PixelOverlap]:
    """Yield exact WGS84 geodesic overlap area with every intersecting raster pixel.

    The caller must provide a raster grid in EPSG:4326. This deliberately avoids
    assuming that a degree-space pixel has a constant or 1-ha area.
    """
    minx, miny, maxx, maxy = geometry_wgs84.bounds
    inv = ~transform
    candidates = [
        inv * (minx, miny), inv * (minx, maxy), inv * (maxx, miny), inv * (maxx, maxy)
    ]
    cols = [p[0] for p in candidates]
    rows = [p[1] for p in candidates]
    c0 = max(0, int(np.floor(min(cols))) - 1)
    c1 = min(width, int(np.ceil(max(cols))) + 1)
    r0 = max(0, int(np.floor(min(rows))) - 1)
    r1 = min(height, int(np.ceil(max(rows))) + 1)
    for row in range(r0, r1):
        for col in range(c0, c1):
            px = pixel_polygon(transform, row, col)
            if not px.intersects(geometry_wgs84):
                continue
            inter = px.intersection(geometry_wgs84)
            area = geodesic_area_ha(inter)
            if area > 0:
                yield PixelOverlap(row=row, col=col, area_ha=area)
