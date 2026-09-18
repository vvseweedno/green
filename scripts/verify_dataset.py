#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

from carbon_mrv.data.catalog import verify_file_catalog
from carbon_mrv.data.local import LocalDataset
from carbon_mrv.data.metadata import MANDATORY_METADATA_FILES, load_official_metadata
from carbon_mrv.data.scene_index import load_scene_rows
from carbon_mrv.geometry.validate import validate_geometry_geojson


def _sample_finite_fraction(src: rasterio.io.DatasetReader, band: int = 1) -> float:
    h = min(src.height, 256)
    w = min(src.width, 256)
    arr = src.read(band, out_shape=(h, w), masked=True)
    data = np.asarray(arr.filled(np.nan), dtype=float)
    return float(np.mean(np.isfinite(data))) if data.size else 0.0


def _id_col(df: pd.DataFrame) -> str | None:
    lower = {c.lower(): c for c in df.columns}
    return next((lower[k] for k in ("aoi_id", "area_id", "site_id", "id", "name") if k in lower), None)


def _feature_id(feature: dict) -> str | None:
    props = feature.get("properties") or {}
    return str(props.get("request_id") or props.get("id") or props.get("name") or feature.get("id") or "") or None


def main() -> int:
    ap = argparse.ArgumentParser(description="Strict integrity and schema checks for the official competition dataset")
    ap.add_argument("dataset", nargs="?", default="data/raw")
    args = ap.parse_args()
    root = Path(args.dataset).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    evidence: dict = {}

    if not root.exists():
        print(json.dumps({"ok": False, "errors": [f"dataset root does not exist: {root}"]}, indent=2))
        return 2

    bundle = load_official_metadata(root)
    for name in bundle["missing"]:
        errors.append(f"missing required file: {name}")
    evidence["metadata_files"] = bundle["files"]

    catalog_path = next(iter(root.rglob("file_catalog.csv")), None)
    if catalog_path is not None:
        try:
            checks = verify_file_catalog(root, catalog_path)
            bad = [c for c in checks if not c.exists or c.size_ok is False or c.hash_ok is False]
            evidence["file_catalog_entries"] = len(checks)
            for c in bad:
                errors.append(f"catalog {c.message}: {c.path}")
        except Exception as exc:
            errors.append(f"file_catalog validation failed: {exc}")

    dataset = LocalDataset(root)
    try:
        parents = dataset.parent_aois()
        parent_ids = {p.aoi_id for p in parents}
        evidence["parent_aois"] = sorted(parent_ids)
    except Exception as exc:
        parent_ids = set()
        errors.append(f"areas.geojson invalid: {exc}")

    areas_csv = next(iter(root.rglob("areas.csv")), None)
    if areas_csv is not None:
        try:
            df = pd.read_csv(areas_csv)
            col = _id_col(df)
            if col is None:
                errors.append("areas.csv missing AOI id column")
            elif parent_ids:
                csv_ids = {str(x) for x in df[col].dropna()}
                if csv_ids != parent_ids:
                    errors.append(f"areas.csv/areas.geojson AOI IDs differ: csv={sorted(csv_ids)} geojson={sorted(parent_ids)}")
        except Exception as exc:
            errors.append(f"areas.csv invalid: {exc}")

    try:
        baselines = dataset.baseline_trajectories()
        missing_baseline = sorted(parent_ids - set(baselines))
        if missing_baseline:
            errors.append(f"baseline.csv missing parent AOIs: {missing_baseline}")
        evidence["baseline_aois"] = sorted(baselines)
        baseline_consistency = dataset.baseline_consistency_report()
        evidence["baseline_formula_consistency"] = baseline_consistency
        if baseline_consistency["mismatch_count"] > 0:
            errors.append(
                "baseline.csv disagrees with mandated formula: "
                f"{baseline_consistency['mismatch_count']} value(s)"
            )
    except Exception as exc:
        errors.append(f"baseline.csv invalid: {exc}")

    params = bundle.get("methodology_parameters") or {}
    if not params:
        errors.append("parameters.csv contains no readable methodology parameters")
    evidence["methodology_parameters"] = params

    try:
        scene_rows = load_scene_rows(root)
        evidence["scenes"] = len(scene_rows)
        if not scene_rows:
            errors.append("scenes.csv contains no scenes")
        for row in scene_rows:
            if not row.reflectance_path.exists():
                errors.append(f"missing Sentinel reflectance: {row.reflectance_path}")
                continue
            if not row.scl_path.exists():
                errors.append(f"missing Sentinel SCL: {row.scl_path}")
                continue
            with rasterio.open(row.reflectance_path) as refl, rasterio.open(row.scl_path) as scl:
                if refl.crs is None or scl.crs is None:
                    errors.append(f"Sentinel scene missing CRS: {row.reflectance_path}")
                if refl.count < 6:
                    errors.append(f"Sentinel reflectance must have >=6 bands: {row.reflectance_path}")
                if scl.count < 1:
                    errors.append(f"SCL missing band: {row.scl_path}")
                if refl.shape != scl.shape or refl.transform != scl.transform or str(refl.crs) != str(scl.crs):
                    errors.append(f"Sentinel reflectance/SCL grid mismatch: {row.reflectance_path}")
                if any(abs(float(x) - 1.0) > 1e-9 for x in refl.scales[:6]):
                    errors.append(f"Prepared Sentinel reflectance scale must be 1: {row.reflectance_path}")
                if any(abs(float(x)) > 1e-9 for x in refl.offsets[:6]):
                    errors.append(f"Prepared Sentinel reflectance offset must be 0: {row.reflectance_path}")
    except Exception as exc:
        errors.append(f"scenes.csv/scene metadata validation failed: {exc}")

    cci_paths = sorted(root.rglob("CCI_Biomass_*.tif"))
    if not cci_paths:
        errors.append("no CCI_Biomass_*.tif files found")
    for path in cci_paths:
        try:
            with rasterio.open(path) as src:
                if str(src.crs).upper() not in {"EPSG:4326", "OGC:CRS84"}:
                    errors.append(f"CCI raster must be EPSG:4326: {path}")
                if src.count < 2:
                    errors.append(f"CCI biomass needs AGB+AGB_SD bands: {path}")
                if src.nodata is not None:
                    errors.append(f"CCI annual raster unexpectedly has NoData tag (zero is valid): {path}")
                if _sample_finite_fraction(src, 1) == 0:
                    errors.append(f"CCI AGB sample has no finite values: {path}")
        except Exception as exc:
            errors.append(f"CCI raster open failed {path}: {exc}")

    for path in sorted(root.rglob("CCI_Change_2019_2020.tif")):
        try:
            with rasterio.open(path) as src:
                if src.count < 3:
                    errors.append(f"CCI change raster needs delta/SD/flag bands: {path}")
        except Exception as exc:
            errors.append(f"CCI change raster open failed {path}: {exc}")

    for path in root.rglob("*.tif"):
        low = path.name.lower()
        try:
            with rasterio.open(path) as src:
                if src.width <= 0 or src.height <= 0 or src.count <= 0:
                    errors.append(f"invalid raster dimensions: {path}")
                if src.crs is None:
                    errors.append(f"missing CRS: {path}")
                if any(k in low for k in ("lossyear", "treecover2000", "datamask")):
                    if str(src.crs).upper() not in {"EPSG:4326", "OGC:CRS84"}:
                        errors.append(f"GFC raster must be EPSG:4326: {path}")
        except Exception as exc:
            errors.append(f"raster open failed {path}: {exc}")

    sample_path = next(iter(root.rglob("sample_requests.geojson")), None)
    if sample_path is not None:
        try:
            payload = json.loads(sample_path.read_text(encoding="utf-8"))
            features = payload.get("features", [])
            ids = []
            for f in features:
                fid = _feature_id(f)
                if fid:
                    ids.append(fid)
                validate_geometry_geojson(f["geometry"])
            evidence["sample_requests"] = ids
            if "CHECK_TRANSFER_01" not in ids:
                warnings.append("sample_requests.geojson has no explicit CHECK_TRANSFER_01 id; transfer proof must identify intended feature by metadata")
        except Exception as exc:
            errors.append(f"sample_requests.geojson invalid: {exc}")

    if bundle.get("reference_events"):
        evidence["reference_events_count"] = len(bundle["reference_events"])
    else:
        warnings.append("events.csv parsed but contains no reference events")

    result = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "evidence": evidence,
        "required_metadata": list(MANDATORY_METADATA_FILES),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
