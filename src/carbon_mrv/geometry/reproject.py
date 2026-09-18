from __future__ import annotations

from pyproj import CRS, Transformer
from shapely.ops import transform as shp_transform


def reproject_geometry(geometry, src_crs, dst_crs):
    src = CRS.from_user_input(src_crs)
    dst = CRS.from_user_input(dst_crs)
    if src == dst:
        return geometry
    transformer = Transformer.from_crs(src, dst, always_xy=True)
    return shp_transform(transformer.transform, geometry)
