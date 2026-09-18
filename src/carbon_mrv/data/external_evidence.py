from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping

from carbon_mrv.data.modis import valid_burn_mask
from carbon_mrv.geometry.reproject import reproject_geometry


def _rank_paths(root: Path, aoi_id: str, keywords: tuple[str, ...], year: int | None = None) -> list[Path]:
    candidates = []
    keys = tuple(k.lower() for k in keywords)
    for p in root.rglob("*.tif"):
        low = str(p).lower()
        if not all(k in low for k in keys):
            continue
        score = (10 if aoi_id.lower() in low else 0) + (5 if year is not None and str(year) in low else 0)
        candidates.append((score, len(str(p)), p))
    return [p for _, _, p in sorted(candidates, key=lambda x: (-x[0], x[1]))]


def find_raster(root: str | Path, aoi_id: str, *keywords: str, year: int | None = None) -> Path | None:
    matches = _rank_paths(Path(root), aoi_id, tuple(keywords), year)
    return matches[0] if matches else None


def read_masked_band(path: str | Path, geometry_wgs84, band: int = 1) -> np.ndarray:
    with rasterio.open(path) as src:
        if src.crs is None:
            raise ValueError(f"Raster has no CRS: {path}")
        geom = reproject_geometry(geometry_wgs84, "EPSG:4326", src.crs)
        arr, _ = mask(src, [mapping(geom)], crop=True, filled=False, indexes=band)
        return np.asarray(arr.filled(np.nan), dtype=float)


def gfc_event_evidence(dataset_root: str | Path, aoi_id: str, geometry_wgs84, loss_year: int) -> dict | None:
    path = find_raster(dataset_root, aoi_id, "lossyear")
    if path is None:
        return None
    arr = read_masked_band(path, geometry_wgs84)
    code = loss_year - 2000
    finite = np.isfinite(arr)
    if not np.any(finite & (arr == code)):
        return None
    return {
        "family": "gfc", "strength": "strong", "direction": "loss",
        "date_min": date(loss_year, 1, 1), "date_max": date(loss_year, 12, 31),
        "path": str(path), "matching_pixels": int(np.sum(finite & (arr == code))),
    }


def _open_aligned_pair(burn_path: Path, qa_path: Path, geometry_wgs84):
    with rasterio.open(burn_path) as burn_src, rasterio.open(qa_path) as qa_src:
        if burn_src.crs is None or qa_src.crs is None:
            raise ValueError("MODIS evidence raster missing CRS")
        if str(burn_src.crs) != str(qa_src.crs) or burn_src.transform != qa_src.transform or burn_src.shape != qa_src.shape:
            raise ValueError("MODIS Burn_Date and QA grids are not aligned")
        geom = reproject_geometry(geometry_wgs84, "EPSG:4326", burn_src.crs)
        burn, _ = mask(burn_src, [mapping(geom)], crop=True, filled=False, indexes=1)
        qa, _ = mask(qa_src, [mapping(geom)], crop=True, filled=False, indexes=1)
        return np.asarray(burn.filled(0), dtype=np.int16), np.asarray(qa.filled(0), dtype=np.uint8)


def modis_fire_evidence(dataset_root: str | Path, aoi_id: str, geometry_wgs84, year: int) -> dict | None:
    root = Path(dataset_root)
    burn_path = find_raster(root, aoi_id, "burn", "date", year=year)
    qa_path = find_raster(root, aoi_id, "qa", year=year)
    if burn_path is None or qa_path is None:
        return None
    try:
        burn, qa = _open_aligned_pair(burn_path, qa_path, geometry_wgs84)
    except ValueError:
        return None
    valid = valid_burn_mask(burn, qa)
    if not np.any(valid):
        return None
    days = burn[valid].astype(int)
    uncertainty_path = find_raster(root, aoi_id, "burn", "uncert", year=year)
    pad = 0
    if uncertainty_path is not None:
        try:
            unc = read_masked_band(uncertainty_path, geometry_wgs84)
            if unc.shape == burn.shape:
                uv = unc[valid]
                uv = uv[np.isfinite(uv) & (uv >= 0)]
                if uv.size:
                    pad = int(np.ceil(np.nanmax(uv)))
        except Exception:
            pass
    lo_day = max(1, int(days.min()) - pad)
    hi_day = min(366, int(days.max()) + pad)
    start = date(year, 1, 1) + timedelta(days=lo_day - 1)
    end = date(year, 1, 1) + timedelta(days=hi_day - 1)
    return {
        "family": "modis", "strength": "strong", "direction": "loss",
        "date_min": start, "date_max": end, "supports_fire": True,
        "burn_path": str(burn_path), "qa_path": str(qa_path),
        "matching_pixels": int(np.sum(valid)), "uncertainty_days_max": pad,
    }
