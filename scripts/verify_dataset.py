#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import rasterio

from carbon_mrv.data.catalog import verify_file_catalog

REQUIRED = [
    "areas.csv", "areas.geojson", "sample_requests.geojson", "scenes.csv", "scene_metadata.json",
    "events.csv", "sources.csv", "file_catalog.csv", "baseline.csv", "parameters.csv",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", nargs="?", default="data/raw")
    args = ap.parse_args()
    root = Path(args.dataset)
    errors, warnings = [], []
    if not root.exists():
        print(json.dumps({"ok": False, "errors": [f"dataset root does not exist: {root}"]}, indent=2))
        return 2
    found = {}
    for name in REQUIRED:
        matches = list(root.rglob(name))
        if not matches:
            errors.append(f"missing required file: {name}")
        else:
            found[name] = str(matches[0])
    if "file_catalog.csv" in found:
        try:
            checks = verify_file_catalog(root, found["file_catalog.csv"])
            for c in checks:
                if not c.exists or c.size_ok is False or c.hash_ok is False:
                    errors.append(f"catalog {c.message}: {c.path}")
        except Exception as exc:
            errors.append(f"file_catalog validation failed: {exc}")
    tif_count = 0
    for path in root.rglob("*.tif"):
        tif_count += 1
        try:
            with rasterio.open(path) as src:
                if src.count <= 0 or src.width <= 0 or src.height <= 0:
                    errors.append(f"invalid raster dimensions: {path}")
                if src.crs is None:
                    errors.append(f"missing CRS: {path}")
        except Exception as exc:
            errors.append(f"raster open failed {path}: {exc}")
    if tif_count == 0:
        warnings.append("no GeoTIFFs found")
    result = {"ok": not errors, "errors": errors, "warnings": warnings, "found": found, "tif_count": tif_count}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
