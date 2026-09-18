from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.io import MemoryFile


def _stretch_rgb(arr: np.ndarray) -> np.ndarray:
    out = np.zeros(arr.shape, dtype=np.uint8)
    for i in range(3):
        band = np.asarray(arr[i], dtype=float)
        finite = np.isfinite(band)
        if not np.any(finite):
            continue
        lo, hi = np.nanpercentile(band[finite], [2, 98])
        if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            lo = float(np.nanmin(band[finite]))
            hi = float(np.nanmax(band[finite]))
        if hi <= lo:
            continue
        scaled = np.clip((band - lo) / (hi - lo), 0, 1)
        scaled[~finite] = 0
        out[i] = np.round(scaled * 255).astype(np.uint8)
    return out


def render_prepared_rgb_png(path: str | Path, *, max_size: int = 900) -> bytes:
    """Render a small true-color preview from prepared B02,B03,B04,B8A,B11,B12 raster.

    Band order in the competition raster is B02,B03,B04,B8A,B11,B12, therefore
    RGB uses bands 3,2,1. This is visualization only and never feeds carbon/change math.
    """
    path = Path(path)
    with rasterio.open(path) as src:
        if src.count < 3:
            raise ValueError("Sentinel reflectance preview needs at least B02/B03/B04")
        scale = min(1.0, max_size / max(src.width, src.height))
        width = max(1, int(round(src.width * scale)))
        height = max(1, int(round(src.height * scale)))
        arr = src.read(
            [3, 2, 1],
            out_shape=(3, height, width),
            resampling=Resampling.bilinear,
            masked=True,
        )
        rgb = _stretch_rgb(np.asarray(arr.filled(np.nan), dtype=float))

    with MemoryFile() as mem:
        with mem.open(
            driver="PNG",
            width=rgb.shape[2],
            height=rgb.shape[1],
            count=3,
            dtype="uint8",
        ) as dst:
            dst.write(rgb)
        return mem.read()
