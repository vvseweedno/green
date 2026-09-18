from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping

from carbon_mrv.data.cci import read_cci_clip
from carbon_mrv.uncertainty.temporal import implicit_rho


def find_cci_change_path(dataset_root: str | Path, aoi_id: str) -> Path | None:
    root = Path(dataset_root)
    candidates = [
        p for p in root.rglob("CCI_Change_2019_2020.tif")
        if aoi_id.lower() in str(p).lower()
    ]
    if candidates:
        return candidates[0]
    all_matches = list(root.rglob("CCI_Change_2019_2020.tif"))
    return all_matches[0] if len(all_matches) == 1 else None


def temporal_rho_from_official_change(
    dataset_root: str | Path,
    aoi_id: str,
    geometry_wgs84,
) -> dict | None:
    root = Path(dataset_root)
    annual_2019 = next(
        (p for p in root.rglob("CCI_Biomass_2019.tif") if aoi_id.lower() in str(p).lower()),
        None,
    )
    annual_2020 = next(
        (p for p in root.rglob("CCI_Biomass_2020.tif") if aoi_id.lower() in str(p).lower()),
        None,
    )
    change_path = find_cci_change_path(root, aoi_id)
    if annual_2019 is None or annual_2020 is None or change_path is None:
        return None

    c19 = read_cci_clip(annual_2019, geometry_wgs84)
    c20 = read_cci_clip(annual_2020, geometry_wgs84)
    if c19.sd.shape != c20.sd.shape or tuple(c19.transform) != tuple(c20.transform):
        return None

    with rasterio.open(change_path) as src:
        if src.count < 3:
            raise ValueError("CCI_Change_2019_2020 must contain delta AGB, change SD and quality flag")
        out, transform = mask(src, [mapping(geometry_wgs84)], crop=True, filled=False)
        delta = np.asarray(out[0].filled(np.nan), dtype=float)
        sd_delta = np.asarray(out[1].filled(np.nan), dtype=float)
        flag = np.asarray(out[2].filled(np.nan), dtype=float)

    if sd_delta.shape != c19.sd.shape or tuple(transform) != tuple(c19.transform):
        return None
    diag = implicit_rho(c19.sd, c20.sd, sd_delta)
    finite_flag = flag[np.isfinite(flag)]
    unique, counts = np.unique(finite_flag, return_counts=True) if finite_flag.size else ([], [])
    return {
        **asdict(diag),
        "source": str(change_path.relative_to(root.resolve())),
        "delta_agb_finite_fraction": float(np.mean(np.isfinite(delta))),
        "change_sd_finite_fraction": float(np.mean(np.isfinite(sd_delta))),
        "quality_flag_histogram": {
            str(int(k) if float(k).is_integer() else float(k)): int(v)
            for k, v in zip(unique, counts, strict=True)
        },
        "interpretation": (
            "Diagnostic implied temporal correlation from official 2019-2020 change SD; "
            "quality flag is reported but not reinterpreted without documented flag semantics."
        ),
    }
