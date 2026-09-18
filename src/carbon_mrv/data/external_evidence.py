from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.mask import mask
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from carbon_mrv.data.modis import valid_burn_mask
from carbon_mrv.geometry.reproject import reproject_geometry


def _rank_paths(root: Path, aoi_id: str, keywords: tuple[str, ...], year: int | None = None) -> list[Path]:
    candidates = []
    keys = tuple(k.lower() for k in keywords)
    for p in root.rglob("*.tif"):
        low = str(p).lower()
        if not all(k in low for k in keys):
            continue
        score = 0
        if aoi_id.lower() in low:
            score += 10
        if year is not None and str(year) in low:
            score += 5
        candidates.append((score, len(str(p)), p))
    return [p for _, _, p in sorted(candidates, key=lambda x: (-x[0], x[1]))]


def find_raster(root: str | Path, aoi_id: str, *keywords: str, year: int | None = None) -> Path | None:
    matches = _rank_paths(Path(root), aoi_id, tuple(keywords), year)
    return matches[0] if matches else None


def read_masked_band(path: str | Path, geometry_wgs84, band: int = 1) -> np.ndarray:
    arr, _, _ = read_masked_band_with_grid(path, geometry_wgs84, band)
    return arr


def read_masked_band_with_grid(path: str | Path, geometry_wgs84, band: int = 1):
    with rasterio.open(path) as src:
        if src.crs is None:
            raise ValueError(f"Raster has no CRS: {path}")
        geom = reproject_geometry(geometry_wgs84, "EPSG:4326", src.crs)
        arr, transform = mask(src, [mapping(geom)], crop=True, filled=False, indexes=band)
        return np.asarray(arr.filled(np.nan), dtype=float), transform, src.crs


def _support_geometry_wgs84(binary: np.ndarray, transform, crs):
    geoms = [
        shape(geom)
        for geom, value in shapes(
            np.asarray(binary, dtype=np.uint8),
            mask=np.asarray(binary, dtype=bool),
            transform=transform,
        )
        if int(value) == 1
    ]
    if not geoms:
        return None
    merged = unary_union(geoms)
    wgs84 = reproject_geometry(merged, crs, "EPSG:4326")
    return wgs84.__geo_interface__


def gfc_event_evidence(dataset_root: str | Path, aoi_id: str, geometry_wgs84, loss_year: int) -> dict | None:
    path = find_raster(dataset_root, aoi_id, "lossyear")
    if path is None:
        return None
    arr, transform, crs = read_masked_band_with_grid(path, geometry_wgs84)
    code = loss_year - 2000
    finite = np.isfinite(arr)
    matching = finite & (arr == code)
    if not np.any(matching):
        return None
    return {
        "family": "gfc",
        "strength": "strong",
        "direction": "loss",
        "date_min": date(loss_year, 1, 1),
        "date_max": date(loss_year, 12, 31),
        "path": str(path),
        "matching_pixels": int(np.sum(matching)),
        "footprint_geometry_wgs84": _support_geometry_wgs84(
            matching, transform, crs
        ),
        "footprint_kind": "GFC loss-pixel support",
    }


def _read_aligned_crop_with_grid(
    reference_path: Path, other_path: Path, geometry_wgs84, *, fill: int = 0
):
    with rasterio.open(reference_path) as ref, rasterio.open(other_path) as src:
        if ref.crs is None or src.crs is None:
            raise ValueError("MODIS evidence raster missing CRS")
        if str(ref.crs) != str(src.crs) or ref.transform != src.transform or ref.shape != src.shape:
            raise ValueError("MODIS evidence grids are not aligned")
        geom = reproject_geometry(geometry_wgs84, "EPSG:4326", ref.crs)
        arr, transform = mask(src, [mapping(geom)], crop=True, filled=False, indexes=1)
        return np.asarray(arr.filled(fill)), transform, ref.crs


def _read_aligned_crop(reference_path: Path, other_path: Path, geometry_wgs84, *, fill: int = 0):
    arr, _, _ = _read_aligned_crop_with_grid(
        reference_path, other_path, geometry_wgs84, fill=fill
    )
    return arr


def _open_aligned_pair(burn_path: Path, qa_path: Path, geometry_wgs84):
    burn = _read_aligned_crop(burn_path, burn_path, geometry_wgs84, fill=0).astype(np.int16)
    qa = _read_aligned_crop(burn_path, qa_path, geometry_wgs84, fill=0).astype(np.uint8)
    return burn, qa


def _optional_aligned(path: Path | None, burn_path: Path, geometry_wgs84) -> np.ndarray | None:
    if path is None:
        return None
    try:
        return np.asarray(_read_aligned_crop(burn_path, path, geometry_wgs84, fill=0), dtype=float)
    except (ValueError, rasterio.errors.RasterioError):
        return None


def modis_fire_evidence(dataset_root: str | Path, aoi_id: str, geometry_wgs84, year: int) -> dict | None:
    """Build MCD64A1 fire evidence with QA and temporal-observability constraints.

    Burn_Date is accepted only for land pixels with sufficient valid observations. The event
    interval combines Burn_Date_Uncertainty with First_Day/Last_Day where those layers exist.
    A MODIS cell is evidence for timing/cause, never exact burn geometry.
    """
    root = Path(dataset_root)
    burn_path = find_raster(root, aoi_id, "burn", "date", year=year)
    qa_path = find_raster(root, aoi_id, "qa", year=year)
    if burn_path is None or qa_path is None:
        return None
    try:
        burn, burn_transform, burn_crs = _read_aligned_crop_with_grid(
            burn_path, burn_path, geometry_wgs84, fill=0
        )
        qa = _read_aligned_crop(
            burn_path, qa_path, geometry_wgs84, fill=0
        ).astype(np.uint8)
        burn = np.asarray(burn, dtype=np.int16)
    except ValueError:
        return None
    valid = valid_burn_mask(burn, qa)
    if not np.any(valid):
        return None

    uncertainty_path = find_raster(root, aoi_id, "burn", "uncert", year=year)
    first_day_path = find_raster(root, aoi_id, "first", "day", year=year)
    last_day_path = find_raster(root, aoi_id, "last", "day", year=year)
    unc = _optional_aligned(uncertainty_path, burn_path, geometry_wgs84)
    first = _optional_aligned(first_day_path, burn_path, geometry_wgs84)
    last = _optional_aligned(last_day_path, burn_path, geometry_wgs84)

    days = burn[valid].astype(int)
    pads = np.zeros(days.shape, dtype=int)
    if unc is not None and unc.shape == burn.shape:
        uv = unc[valid]
        uv = np.where(np.isfinite(uv) & (uv >= 0), uv, 0)
        pads = np.ceil(uv).astype(int)

    first_v = np.ones(days.shape, dtype=int)
    if first is not None and first.shape == burn.shape:
        fv = first[valid]
        first_v = np.where(np.isfinite(fv) & (fv > 0), fv, 1).astype(int)

    last_v = np.full(days.shape, 366, dtype=int)
    if last is not None and last.shape == burn.shape:
        lv = last[valid]
        last_v = np.where(np.isfinite(lv) & (lv > 0), lv, 366).astype(int)

    low_pixels = np.maximum(np.maximum(1, days - pads), first_v)
    high_pixels = np.minimum(np.minimum(366, days + pads), last_v)
    feasible = low_pixels <= high_pixels
    if not np.any(feasible):
        return None

    lo_day = int(np.min(low_pixels[feasible]))
    hi_day = int(np.max(high_pixels[feasible]))
    start = date(year, 1, 1) + timedelta(days=lo_day - 1)
    end = date(year, 1, 1) + timedelta(days=hi_day - 1)
    return {
        "family": "modis",
        "strength": "strong",
        "direction": "loss",
        "date_min": start,
        "date_max": end,
        "supports_fire": True,
        "burn_path": str(burn_path),
        "qa_path": str(qa_path),
        "uncertainty_path": str(uncertainty_path) if uncertainty_path else None,
        "first_day_path": str(first_day_path) if first_day_path else None,
        "last_day_path": str(last_day_path) if last_day_path else None,
        "matching_pixels": int(np.sum(valid)),
        "temporally_feasible_pixels": int(np.sum(feasible)),
        "uncertainty_days_max": int(np.max(pads)) if pads.size else 0,
        "first_day_constraint_used": first is not None,
        "last_day_constraint_used": last is not None,
        "footprint_geometry_wgs84": _support_geometry_wgs84(
            valid, burn_transform, burn_crs
        ) if np.any(valid) else None,
        "footprint_kind": "coarse MCD64A1 cell support; not exact burn perimeter",
    }
