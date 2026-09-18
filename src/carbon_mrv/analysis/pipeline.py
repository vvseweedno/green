from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from carbon_mrv.carbon.baseline import aggregate_baseline
from carbon_mrv.carbon.credits import calculate_potential_credits
from carbon_mrv.carbon.stock import (
    StockEstimate,
    annualized_emission_intensity,
    stock_difference_emission_tco2e,
    stock_from_weighted_pixels,
)
from carbon_mrv.data.cci import area_weight_grid, exact_weight_vectors, read_cci_clip
from carbon_mrv.data.local import LocalDataset
from carbon_mrv.data.provenance import canonical_json_hash, sha256_file
from carbon_mrv.domain.models import AnalysisRequest
from carbon_mrv.geometry.area import geodesic_area_ha
from carbon_mrv.geometry.validate import validate_geometry_geojson, validate_years
from carbon_mrv.quality.coverage import coverage_result
from carbon_mrv.uncertainty.monte_carlo import run_scenario

LIMITATIONS = [
    "E is a stock-difference expression for the live above-ground woody biomass pool, not a direct atmospheric-emissions measurement.",
    "Potential units Q are scenario outputs for the hackathon and are not certified carbon credits.",
    "Uncertainty bounds are model-based quantiles under stated spatial/temporal dependence assumptions; they are not field-calibrated confidence intervals.",
]


def _sum_stock(parts: list[StockEstimate]) -> StockEstimate:
    area = sum(p.area_ha for p in parts)
    total = sum(p.total_carbon_t for p in parts)
    if area <= 0:
        raise ValueError("No computed carbon-stock area")
    return StockEstimate(area, total, total / area)


def analyze_local(
    request: AnalysisRequest,
    dataset_root: str | Path,
    *,
    simulations: int = 500,
    seed: int = 20260918,
) -> dict[str, Any]:
    validate_years(request.year_start, request.year_end)
    geom, requested_area = validate_geometry_geojson(request.geometry)
    dataset = LocalDataset(dataset_root)
    parent_parts = dataset.intersecting_parents(geom)
    if request.parent_aoi_id:
        parent_parts = [(p, g) for p, g in parent_parts if p.aoi_id == request.parent_aoi_id]
    if not parent_parts:
        raise ValueError("AOI is outside provided parent AOI coverage")

    yearly: list[dict[str, Any]] = []
    stock_by_year: dict[int, StockEstimate] = {}
    provenance_files: dict[str, str] = {}
    parent_year_inputs: dict[tuple[str, int], tuple[Any, Any, Any]] = {}

    for year in range(2019, 2025):
        estimates = []
        for parent, part_geom in parent_parts:
            path = dataset.cci_path(parent.aoi_id, year)
            if path is None:
                continue
            clip = read_cci_clip(path, part_geom)
            agb, sd, areas = exact_weight_vectors(clip, part_geom)
            if agb.size == 0:
                continue
            est = stock_from_weighted_pixels(agb, areas)
            estimates.append(est)
            parent_year_inputs[(parent.aoi_id, year)] = (clip, part_geom, path)
            provenance_files[str(path.relative_to(dataset.root))] = sha256_file(path)
        if estimates:
            total = _sum_stock(estimates)
            stock_by_year[year] = total
            yearly.append({
                "year": year,
                "area_ha": total.area_ha,
                "total_carbon_t": total.total_carbon_t,
                "mean_carbon_t_ha": total.mean_carbon_t_ha,
            })

    if request.year_start not in stock_by_year or request.year_end not in stock_by_year:
        raise ValueError("Required CCI start/end year data are unavailable")

    start = stock_by_year[request.year_start]
    end = stock_by_year[request.year_end]
    computed_area = min(start.area_ha, end.area_ha)
    cov = coverage_result(requested_area, computed_area)
    E = stock_difference_emission_tco2e(start, end)
    e = annualized_emission_intensity(E, computed_area, request.year_start, request.year_end)

    u_parts = []
    for parent, part_geom in parent_parts:
        key0 = (parent.aoi_id, request.year_start)
        key1 = (parent.aoi_id, request.year_end)
        if key0 not in parent_year_inputs or key1 not in parent_year_inputs:
            continue
        c0, _, _ = parent_year_inputs[key0]
        c1, _, _ = parent_year_inputs[key1]
        if c0.agb.shape != c1.agb.shape or tuple(c0.transform) != tuple(c1.transform):
            continue
        weights = area_weight_grid(c0, part_geom)
        try:
            u = run_scenario(
                request.uncertainty_scenario,
                agb0=c0.agb,
                agb1=c1.agb,
                sd0=c0.sd,
                sd1=c1.sd,
                area_ha=weights,
                simulations=simulations,
                seed=seed,
            )
            u_parts.append((parent.aoi_id, u))
        except ValueError:
            continue

    if u_parts:
        lower = sum(u.lower_tco2e for _, u in u_parts)
        upper = sum(u.upper_tco2e for _, u in u_parts)
        uncertainty = {
            "L": lower,
            "U": upper,
            "method": "sum of parent-part model-based correlated Monte Carlo intervals",
            "assumptions": {
                "scenario": request.uncertainty_scenario,
                "simulations": simulations,
                "seed": seed,
                "cross_parent_aggregation": "conservative bound summation",
                "parts": [{"aoi_id": aoi, **asdict(u)} for aoi, u in u_parts],
            },
            "sensitivity": [],
        }
    else:
        lower = upper = None
        uncertainty = None

    baseline_map = dataset.baseline_trajectories()
    baseline_parts = []
    baseline_proof = []
    for parent, part_geom in parent_parts:
        area = geodesic_area_ha(part_geom)
        trajectory = baseline_map.get(parent.aoi_id)
        if trajectory:
            baseline_parts.append((trajectory, area))
            baseline_proof.append({
                "aoi_id": parent.aoi_id,
                "area_ha": area,
                "cbar_2015": trajectory.cbar_2015_tC_ha,
                "cbar_2019": trajectory.cbar_2019_tC_ha,
            })

    baseline_available = len(baseline_parts) == len(parent_parts)
    Ebase = (
        aggregate_baseline(baseline_parts, request.year_start, request.year_end)
        if baseline_available else None
    )

    credits = calculate_potential_credits(
        area_ha=computed_area,
        year_start=request.year_start,
        year_end=request.year_end,
        Ebase=Ebase,
        Eproj=E,
        lower=lower,
        upper=upper,
        full_coverage=cov.reason is None,
        baseline_available=baseline_available,
    )

    config_material = {
        "request": request.model_dump(),
        "simulations": simulations,
        "seed": seed,
        "uncertainty_scenario": request.uncertainty_scenario,
    }

    return {
        "status": "completed",
        "request": {**request.model_dump(), "requested_area_ha": requested_area},
        "coverage": asdict(cov),
        "stock": {
            "yearly": yearly,
            "start": asdict(start),
            "end": asdict(end),
            "delta_c_t": end.total_carbon_t - start.total_carbon_t,
            "E_tco2e": E,
            "e_tco2e_ha_year": e,
            "sign_semantics": "E>0 stock loss; E<0 stock accumulation",
            "carbon_pool": "live above-ground woody biomass",
        },
        "uncertainty": uncertainty,
        "events": [],
        "baseline": {
            "Ebase": Ebase,
            "parent_parts": baseline_proof,
            "available": baseline_available,
        },
        "credits": asdict(credits),
        "provenance": {
            "sources": ["ESA CCI Biomass v7.0", "official methodology/baseline.csv"],
            "checksums": provenance_files,
            "processing_config_hash": canonical_json_hash(config_material),
        },
        "limitations": LIMITATIONS + [
            "Change-event modules never fabricate event objects when required Sentinel/GFC/MODIS inputs are absent."
        ],
        "warnings": ([cov.reason] if cov.reason else []),
    }
