from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping

from carbon_mrv.geometry.area import iter_pixel_overlaps


@dataclass(frozen=True)
class CCIClip:
    agb: np.ndarray
    sd: np.ndarray
    transform: object
    crs: str


def read_cci_clip(path: str | Path, geometry_wgs84) -> CCIClip:
    with rasterio.open(path) as src:
        if str(src.crs).upper() not in {"EPSG:4326", "OGC:CRS84"}:
            raise ValueError(f"CCI raster must be WGS84; got {src.crs}")
        if src.count < 2:
            raise ValueError("CCI biomass raster must contain AGB and AGB_SD bands")
        out, transform = mask(src, [mapping(geometry_wgs84)], crop=True, filled=False)
        agb = np.asarray(out[0].filled(np.nan), dtype=float)
        sd = np.asarray(out[1].filled(np.nan), dtype=float)
        return CCIClip(agb=agb, sd=sd, transform=transform, crs=str(src.crs))


def exact_weight_vectors(clip: CCIClip, geometry_wgs84):
    agbs, sds, areas = [], [], []
    for overlap in iter_pixel_overlaps(geometry_wgs84, clip.transform, clip.agb.shape[0], clip.agb.shape[1]):
        b = float(clip.agb[overlap.row, overlap.col])
        s = float(clip.sd[overlap.row, overlap.col])
        if np.isfinite(b):
            agbs.append(b)
            sds.append(s if np.isfinite(s) and s >= 0 else np.nan)
            areas.append(overlap.area_ha)
    return np.asarray(agbs), np.asarray(sds), np.asarray(areas)


def area_weight_grid(clip: CCIClip, geometry_wgs84) -> np.ndarray:
    weights = np.zeros_like(clip.agb, dtype=float)
    for overlap in iter_pixel_overlaps(geometry_wgs84, clip.transform, clip.agb.shape[0], clip.agb.shape[1]):
        if np.isfinite(clip.agb[overlap.row, overlap.col]):
            weights[overlap.row, overlap.col] = overlap.area_ha
    return weights
