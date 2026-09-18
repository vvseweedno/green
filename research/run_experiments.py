#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from carbon_mrv.analysis.change_pipeline import SceneObservation, annual_from_scenes, detect_transition
from carbon_mrv.analysis.pipeline import analyze_local
from carbon_mrv.carbon.credits import calculate_potential_credits
from carbon_mrv.change.objects import connected_objects
from carbon_mrv.change.transitions import robust_z, transition_maps
from carbon_mrv.data.cci_change import temporal_rho_from_official_change
from carbon_mrv.data.external_evidence import find_raster, gfc_event_evidence, modis_fire_evidence
from carbon_mrv.data.local import LocalDataset
from carbon_mrv.data.scene_index import load_scene_rows
from carbon_mrv.data.sentinel2 import read_prepared_scene
from carbon_mrv.domain.models import AnalysisRequest
from carbon_mrv.geometry.reproject import reproject_geometry

OUT = Path("research/results")
FIG = Path("research/figures")

from plotting import generate_research_figures


def _write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def carbon_and_uncertainty(dataset_root: Path) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    ds = LocalDataset(dataset_root)
    parents = {p.aoi_id: p for p in ds.parent_aois()}
    sites = [x for x in ("RU_MORDOVIA_03", "RU_TVER_01", "RU_MORDOVIA_04") if x in parents]
    if "RU_MORDOVIA_03" not in sites or "RU_TVER_01" not in sites:
        raise RuntimeError("Research requires RU_MORDOVIA_03 and RU_TVER_01 in areas.geojson")
    summaries, sensitivity, baseline_sensitivity, carbon_series = [], [], [], []
    for site in sites:
        geom = parents[site].geometry
        for scenario in ("independent", "moderate", "strong"):
            req = AnalysisRequest(
                geometry=geom.__geo_interface__, year_start=2020, year_end=2022,
                data_mode="offline", parent_aoi_id=site, uncertainty_scenario=scenario,
            )
            res = analyze_local(req, dataset_root, simulations=300, seed=20260918)
            row = {
                "aoi_id": site, "scenario": scenario,
                "E_tco2e": res["stock"]["E_tco2e"],
                "L": (res["uncertainty"] or {}).get("L"),
                "U": (res["uncertainty"] or {}).get("U"),
                "Ebase": res["baseline"].get("Ebase"),
                "Q": res["credits"].get("Q"),
                "H_over_R": res["credits"].get("H_over_R"),
                "coverage_ratio": res["coverage"]["coverage_ratio"],
            }
            sensitivity.append(row)
            if scenario == "moderate":
                summaries.append(row)
                for point in res["stock"].get("yearly", []):
                    carbon_series.append({
                        "aoi_id": site,
                        "year": point["year"],
                        "mean_carbon_t_ha": point["mean_carbon_t_ha"],
                        "total_carbon_t": point["total_carbon_t"],
                    })
                u = res.get("uncertainty") or {}
                L, U = u.get("L"), u.get("U")
                if L is not None and U is not None:
                    for name, ebase in (("official", res["baseline"].get("Ebase")), ("no_change", 0.0)):
                        c = calculate_potential_credits(
                            area_ha=res["coverage"]["computed_area_ha"], year_start=2020, year_end=2022,
                            Ebase=ebase, Eproj=res["stock"]["E_tco2e"], lower=L, upper=U,
                            full_coverage=res["coverage"].get("reason") is None,
                            baseline_available=ebase is not None,
                        )
                        baseline_sensitivity.append({
                            "aoi_id": site, "baseline_scenario": name, "Ebase": ebase, "Q": c.Q, "R": c.R
                        })
    return summaries, sensitivity, baseline_sensitivity, carbon_series


def _load_observations(dataset_root: Path, aoi_id: str, year: int, geometry, months={6, 7, 8}):
    rows = [
        r for r in load_scene_rows(dataset_root)
        if r.aoi_id == aoi_id and r.observed_at.year == year and r.observed_at.month in months
    ]
    if not rows:
        raise RuntimeError(f"No summer Sentinel scenes for {aoi_id}/{year}")
    observations = []
    for row in sorted(rows, key=lambda r: r.observed_at):
        scene = read_prepared_scene(row.reflectance_path, row.scl_path, geometry)
        observations.append(SceneObservation(
            row.observed_at.date(),
            scene.bands,
            scene.scl,
            scene.transform,
            scene.crs,
            row.metadata,
        ))
    return observations


def _external_support(
    dataset_root: Path,
    aoi_id: str,
    objects,
    object_crs: str,
    evidence_year: int,
) -> dict[str, float | int | None]:
    total_area = sum(o.area_ha for o in objects)
    gfc_available = find_raster(dataset_root, aoi_id, "lossyear") is not None
    modis_available = (
        find_raster(dataset_root, aoi_id, "burn", "date", year=evidence_year) is not None
        and find_raster(dataset_root, aoi_id, "qa", year=evidence_year) is not None
    )
    gfc_objects = modis_objects = 0
    gfc_area = modis_area = 0.0
    for obj in objects:
        geom_wgs84 = reproject_geometry(obj.geometry, object_crs, "EPSG:4326")
        if gfc_available and gfc_event_evidence(
            dataset_root, aoi_id, geom_wgs84, evidence_year
        ):
            gfc_objects += 1
            gfc_area += obj.area_ha
        if modis_available and modis_fire_evidence(
            dataset_root, aoi_id, geom_wgs84, evidence_year
        ):
            modis_objects += 1
            modis_area += obj.area_ha
    n = len(objects)
    return {
        "gfc_available": gfc_available,
        "gfc_object_support_rate": (
            gfc_objects / n if gfc_available and n else None
        ),
        "gfc_area_support_rate": (
            gfc_area / total_area if gfc_available and total_area > 0 else None
        ),
        "modis_available": modis_available,
        "modis_object_support_rate": (
            modis_objects / n if modis_available and n else None
        ),
        "modis_area_support_rate": (
            modis_area / total_area if modis_available and total_area > 0 else None
        ),
        "detected_object_count": n,
        "detected_area_ha": total_area,
    }


def change_method_comparison(dataset_root: Path) -> list[dict]:
    ds = LocalDataset(dataset_root)
    parents = {p.aoi_id: p for p in ds.parent_aois()}
    rows = []
    for site in ("RU_MORDOVIA_03", "RU_TVER_01"):
        if site not in parents:
            continue
        geometry = parents[site].geometry
        before_obs = _load_observations(dataset_root, site, 2020, geometry)
        after_obs = _load_observations(dataset_root, site, 2021, geometry)
        before, _ = annual_from_scenes(before_obs)
        after, _ = annual_from_scenes(after_obs)
        d_nbr = before["NBR"] - after["NBR"]
        z_nbr = robust_z(d_nbr)
        mask_a = z_nbr >= 2.5
        tr_b = transition_maps(
            before, after, z_threshold=2.5, min_index_agreement=2, min_observations=1
        )
        tr_c = transition_maps(
            before, after, z_threshold=2.5, min_index_agreement=2, min_observations=2
        )
        for method, mask, score in (
            ("A_dNBR", mask_a, z_nbr),
            ("B_multi_index", tr_b.disturbance, tr_b.score),
            ("C_multi_index_temporal", tr_c.disturbance, tr_c.score),
        ):
            objects = connected_objects(
                mask,
                score,
                before_obs[0].transform,
                crs=before_obs[0].crs,
                min_area_ha=0.25,
            )
            support = _external_support(
                dataset_root, site, objects, before_obs[0].crs, 2021
            )
            rows.append({
                "aoi_id": site,
                "transition": "2020-2021",
                "method": method,
                **support,
                "detected_pixels": int(mask.sum()),
                "observation_coverage_before_mean": float(
                    np.mean(before["valid_observation_count"])
                ),
                "observation_coverage_after_mean": float(
                    np.mean(after["valid_observation_count"])
                ),
                "external_evidence_note": (
                    "GFC/MODIS support rates are satellite-to-satellite evidence agreement, "
                    "not ground-truth precision/recall."
                ),
            })
    return rows


def temporal_dependence_diagnostics(dataset_root: Path) -> list[dict]:
    ds = LocalDataset(dataset_root)
    rows = []
    for parent in ds.parent_aois():
        diagnostic = temporal_rho_from_official_change(
            dataset_root, parent.aoi_id, parent.geometry
        )
        if diagnostic is not None:
            rows.append({"aoi_id": parent.aoi_id, **diagnostic})
    return rows


def threshold_sensitivity(dataset_root: Path) -> list[dict]:
    ds = LocalDataset(dataset_root)
    parents = {p.aoi_id: p for p in ds.parent_aois()}
    site = "RU_MORDOVIA_03"
    geometry = parents[site].geometry
    before_obs = _load_observations(dataset_root, site, 2020, geometry)
    after_obs = _load_observations(dataset_root, site, 2021, geometry)
    rows = []
    for z in (1.5, 2.0, 2.5, 3.0, 3.5):
        res = detect_transition(
            before_obs, after_obs, z_threshold=z, min_index_agreement=2, min_area_ha=0.25
        )
        rows.append({
            "aoi_id": site,
            "z_threshold": z,
            "detected_area_ha": sum(o.area_ha for o in res["loss_objects"]),
            "object_count": len(res["loss_objects"]),
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/raw")
    args = ap.parse_args()
    root = Path(args.dataset)
    if not root.exists():
        raise SystemExit("Dataset unavailable: research refuses to fabricate results")
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    summaries, uncertainty, baseline, carbon_series = carbon_and_uncertainty(root)
    _write_csv(OUT / "site_summary.csv", summaries)
    _write_csv(OUT / "carbon_series.csv", carbon_series)
    _write_csv(OUT / "uncertainty_sensitivity.csv", uncertainty)
    _write_csv(OUT / "baseline_sensitivity.csv", baseline)
    _write_csv(
        OUT / "temporal_rho_diagnostic.csv",
        temporal_dependence_diagnostics(root),
    )
    try:
        changes = change_method_comparison(root)
        thresholds = threshold_sensitivity(root)
        temporal = temporal_dependence_diagnostics(root)
        _write_csv(OUT / "change_method_comparison.csv", changes)
        _write_csv(OUT / "change_threshold_sensitivity.csv", thresholds)
        _write_csv(OUT / "temporal_rho_diagnostic.csv", temporal)
        generate_research_figures(
            carbon_series=carbon_series,
            uncertainty=uncertainty,
            baseline=baseline,
            changes=changes,
            thresholds=thresholds,
            temporal=temporal,
            output_dir=FIG,
        )
    except Exception as exc:
        (OUT / "change_experiment_error.txt").write_text(str(exc), encoding="utf-8")
        raise
    print(json.dumps({
        "ok": True,
        "results": [str(p) for p in sorted(OUT.glob("*"))],
        "figures": [str(p) for p in sorted(FIG.glob("*.png"))],
    }, indent=2))


if __name__ == "__main__":
    main()
