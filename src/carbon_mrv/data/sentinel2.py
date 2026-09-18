from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping

from carbon_mrv.geometry.reproject import reproject_geometry

BANDS = ("B02", "B03", "B04", "B8A", "B11", "B12")


@dataclass(frozen=True)
class PreparedScene:
    bands: dict[str, np.ndarray]
    scl: np.ndarray
    transform: object
    crs: str


def read_prepared_scene(reflectance_path: str | Path, scl_path: str | Path, geometry_wgs84) -> PreparedScene:
    """Read competition-prepared Sentinel-2 without reapplying /10000 scaling.

    Request geometries are WGS84 and are transformed to the raster CRS before masking.
    """
    with rasterio.open(reflectance_path) as src:
        if src.crs is None:
            raise ValueError("Prepared reflectance raster has no CRS")
        if src.count < 6:
            raise ValueError("Prepared reflectance raster must have six bands B02,B03,B04,B8A,B11,B12")
        geom_src = reproject_geometry(geometry_wgs84, "EPSG:4326", src.crs)
        out, transform = mask(src, [mapping(geom_src)], crop=True, filled=True, nodata=np.nan)
        bands = {name: np.asarray(out[i], dtype=np.float32) for i, name in enumerate(BANDS)}
        crs = str(src.crs)
    with rasterio.open(scl_path) as src:
        if src.crs is None:
            raise ValueError("Prepared SCL raster has no CRS")
        geom_scl = reproject_geometry(geometry_wgs84, "EPSG:4326", src.crs)
        scl, scl_transform = mask(src, [mapping(geom_scl)], crop=True, filled=True, nodata=0)
        if str(src.crs) != crs or tuple(scl_transform) != tuple(transform) or scl.shape[1:] != next(iter(bands.values())).shape:
            raise ValueError("Prepared SCL and reflectance grids must align in CRS/transform/shape")
    return PreparedScene(bands=bands, scl=np.asarray(scl[0], dtype=np.uint8), transform=transform, crs=crs)
