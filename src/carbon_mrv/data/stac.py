from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.features import geometry_window
from rasterio.vrt import WarpedVRT
from shapely.geometry import mapping
from shapely.ops import transform as shp_transform

from carbon_mrv.quality.scl import scl_quality_summary

EARTH_SEARCH = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"
ASSETS = {
    "B02": "blue",
    "B03": "green",
    "B04": "red",
    "B8A": "nir08",
    "B11": "swir16",
    "B12": "swir22",
    "SCL": "scl",
}


@dataclass(frozen=True)
class Candidate:
    item: Any
    valid_fraction: float
    strict_valid_fraction: float
    low_confidence_fraction: float
    tile_cloud_cover: float | None


def open_catalog(url: str = EARTH_SEARCH):
    try:
        from pystac_client import Client
    except ImportError as exc:
        raise RuntimeError("Install pystac-client to use online STAC acquisition") from exc
    return Client.open(url)


def search_items(geometry_geojson: dict, start: str, end: str, *, limit: int = 24, catalog=None):
    client = catalog or open_catalog()
    search = client.search(
        collections=[COLLECTION],
        intersects=geometry_geojson,
        datetime=f"{start}/{end}",
        max_items=limit,
    )
    return list(search.items())


def _asset_scale_offset(item, key: str) -> tuple[float, float]:
    asset = item.assets[key]
    bands = asset.extra_fields.get("raster:bands") or []
    if bands:
        return float(bands[0].get("scale", 1.0)), float(bands[0].get("offset", 0.0))
    return 1.0, 0.0


def _geometry_in_crs(geometry_wgs84, crs):
    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    return shp_transform(transformer.transform, geometry_wgs84)


def read_asset_on_20m_grid(item, geometry_wgs84, asset_key: str, *, reference_key: str = "nir08"):
    ref_href = item.assets[reference_key].href
    with rasterio.open(ref_href) as ref:
        geom_ref = _geometry_in_crs(geometry_wgs84, ref.crs)
        window = geometry_window(ref, [mapping(geom_ref)], pad_x=0, pad_y=0)
        ref_transform = ref.window_transform(window)
        height, width = int(window.height), int(window.width)
        ref_crs = ref.crs

    href = item.assets[asset_key].href
    resampling = Resampling.nearest if asset_key == "scl" else Resampling.bilinear
    with rasterio.open(href) as src:
        with WarpedVRT(
            src,
            crs=ref_crs,
            transform=ref_transform,
            width=width,
            height=height,
            resampling=resampling,
            nodata=src.nodata,
        ) as vrt:
            arr = vrt.read(1, masked=True).filled(np.nan if asset_key != "scl" else 0)
    if asset_key != "scl":
        scale, offset = _asset_scale_offset(item, asset_key)
        arr = np.asarray(arr, dtype=np.float32) * scale + offset
    return arr, ref_transform, str(ref_crs)


def assess_candidate(item, geometry_wgs84) -> Candidate:
    scl, _, _ = read_asset_on_20m_grid(item, geometry_wgs84, "scl")
    q = scl_quality_summary(scl)
    cc = item.properties.get("eo:cloud_cover")
    return Candidate(
        item,
        q["valid_fraction"],
        q["strict_valid_fraction"],
        q["low_confidence_fraction"],
        cc,
    )


def rank_candidates(items, geometry_wgs84, *, max_assessed: int = 12) -> list[Candidate]:
    # Tile cloud cover is only a pre-filter. Final ordering uses AOI-valid SCL coverage.
    pre = sorted(items, key=lambda it: float(it.properties.get("eo:cloud_cover", 100.0)))[:max_assessed]
    assessed = [assess_candidate(it, geometry_wgs84) for it in pre]
    return sorted(
        assessed,
        key=lambda c: (c.strict_valid_fraction, c.valid_fraction, -(c.tile_cloud_cover or 100.0)),
        reverse=True,
    )


def read_scene(item, geometry_wgs84) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    arrays: dict[str, np.ndarray] = {}
    transform = None
    crs = None
    scales = {}
    for public_name, asset_key in ASSETS.items():
        arr, transform, crs = read_asset_on_20m_grid(item, geometry_wgs84, asset_key)
        arrays[public_name] = arr
        if asset_key != "scl":
            scale, offset = _asset_scale_offset(item, asset_key)
            scales[public_name] = {"scale": scale, "offset": offset}
    metadata = {
        "item_id": item.id,
        "datetime": item.datetime.isoformat() if item.datetime else item.properties.get("datetime"),
        "collection": item.collection_id,
        "processing_baseline": item.properties.get("s2:processing_baseline")
        or item.properties.get("processing:version"),
        "tile_cloud_cover": item.properties.get("eo:cloud_cover"),
        "scale_offset": scales,
        "source_assets": {k: item.assets[v].href for k, v in ASSETS.items()},
        "transform": tuple(transform) if transform is not None else None,
        "crs": crs,
    }
    return arrays, metadata
