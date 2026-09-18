from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping

BANDS = ("B02", "B03", "B04", "B8A", "B11", "B12")


@dataclass(frozen=True)
class PreparedScene:
    bands: dict[str, np.ndarray]
    scl: np.ndarray
    transform: object
    crs: str


def read_prepared_scene(reflectance_path: str | Path, scl_path: str | Path, geometry) -> PreparedScene:
    """Read competition-prepared Sentinel-2 without reapplying /10000 scaling."""
    with rasterio.open(reflectance_path) as src:
        if src.count < 6:
            raise ValueError("Prepared reflectance raster must have six bands B02,B03,B04,B8A,B11,B12")
        out, transform = mask(src, [mapping(geometry)], crop=True, filled=True, nodata=np.nan)
        bands = {name: np.asarray(out[i], dtype=np.float32) for i, name in enumerate(BANDS)}
        crs = str(src.crs)
    with rasterio.open(scl_path) as src:
        scl, scl_transform = mask(src, [mapping(geometry)], crop=True, filled=True, nodata=0)
        if tuple(scl_transform) != tuple(transform) or scl.shape[1:] != next(iter(bands.values())).shape:
            raise ValueError("Prepared SCL and reflectance grids must align")
    return PreparedScene(bands=bands, scl=np.asarray(scl[0], dtype=np.uint8), transform=transform, crs=crs)
