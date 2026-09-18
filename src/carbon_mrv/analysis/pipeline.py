from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import os
from typing import Any

import numpy as np
from affine import Affine

from carbon_mrv.analysis.change_pipeline import (
    SceneObservation,
    detect_transition,
    diagnostic_post_signal,
    fused_event_record,
    sentinel_evidence,
)
from carbon_mrv.carbon.baseline import aggregate_baseline
from carbon_mrv.carbon.contribution import event_emission_contribution
from carbon_mrv.carbon.credits import calculate_potential_credits
from carbon_mrv.carbon.stock import (
    CF,
    CO2_PER_C,
    StockEstimate,
    annualized_emission_intensity,
    stock_difference_emission_tco2e,
    stock_from_weighted_pixels,
)
from carbon_mrv.change.fusion import Evidence
from carbon_mrv.data.cache import ArrayCache
from carbon_mrv.data.cci import area_weight_grid, exact_weight_vectors, read_cci_clip
from carbon_mrv.data.cci_change import temporal_rho_from_official_change
from carbon_mrv.data.external_evidence import gfc_event_evidence, modis_fire_evidence
from carbon_mrv.data.local import LocalDataset
from carbon_mrv.data.metadata import compact_metadata_provenance, load_official_metadata
from carbon_mrv.data.provenance import canonical_json_hash, sha256_file
from carbon_mrv.data.scene_index import load_scene_rows
from carbon_mrv.data.sentinel2 import read_prepared_scene
from carbon_mrv.data.stac import rank_candidates, read_scene, search_items
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


def _load_observations(
    scene_rows,
    aoi_id: str,
    year: int,
    geometry,
    dataset_root: Path,
    months: frozenset[int] = frozenset({6, 7, 8}),
) -> list[SceneObservation]:
    rows = [
        r for r in scene_rows
        if r.aoi_id == aoi_id
        and r.observed_at.year == year
        and r.observed_at.month in months
    ]
    observations = []
    for row in sorted(rows, key=lambda r: r.observed_at):
        scene = read_prepared_scene(row.reflectance_path, row.scl_path, geometry)
        try:
            reflectance_rel = str(row.reflectance_path.resolve().relative_to(dataset_root.resolve()))
        except ValueError:
            reflectance_rel = None
        try:
            scl_rel = str(row.scl_path.resolve().relative_to(dataset_root.resolve()))
        except ValueError:
            scl_rel = None
        scene_metadata = {
            **(row.metadata or {}),
            "scene_id": row.scene_id or (row.metadata or {}).get("scene_id"),
            "reflectance_path": reflectance_rel,
            "scl_path": scl_rel,
        }
        observations.append(
            SceneObservation(
                row.observed_at.date(),
                scene.bands,
                scene.scl,
                scene.transform,
                scene.crs,
                scene_metadata,
            )
        )
    return observations


def _observation_from_cached(arrays: dict, metadata: dict) -> SceneObservation:
    transform_values = metadata.get("transform")
    if not transform_values or not metadata.get("crs"):
        raise ValueError("Cached Sentinel scene is missing transform/CRS metadata")
    transform = Affine(*list(transform_values)[:6])
    observed = metadata.get("datetime")
    if not observed:
        raise ValueError("Cached Sentinel scene is missing datetime")
    observed_on = datetime.fromisoformat(str(observed).replace("Z", "+00:00")).date()
    bands = {name: np.asarray(arrays[name]) for name in ("B02","B03","B04","B8A","B11","B12")}
    scene_meta = {
        **metadata,
        "scene_id": metadata.get("item_id"),
        "processing_baseline": metadata.get("processing_baseline"),
        "radiometry": metadata.get("scale_offset"),
        "artifact_sha256": metadata.get("sha256"),
        "acquisition_mode": metadata.get("acquisition_mode", "cache"),
    }
    return SceneObservation(
        observed_on,
        bands,
        np.asarray(arrays["SCL"], dtype=np.uint8),
        transform,
        str(metadata["crs"]),
        scene_meta,
    )


def _stac_observations(
    geometry,
    year: int,
    *,
    mode: str,
    warnings: list[str],
    count: int = 2,
) -> list[SceneObservation]:
    start_date = f"{year}-06-01"
    end_date = f"{year}-08-31"
    geometry_json = geometry.__geo_interface__
    request_hash = canonical_json_hash({
        "geometry": geometry_json,
        "start": start_date,
        "end": end_date,
    })
    cache_root = Path(os.getenv("CARBON_MRV_CACHE", "data/cache/sentinel2"))
    cache = ArrayCache(cache_root)

    if mode in {"auto", "offline"}:
        try:
            replay = cache.replay_by_request_hash(request_hash)
            if replay:
                observations = [
                    _observation_from_cached(arrays, {**meta, "acquisition_mode": "offline_cache"})
                    for arrays, meta in replay[:count]
                ]
                return sorted(observations, key=lambda item: item.observed_on)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Sentinel cache replay failed for {year}: {exc}")
        if mode == "offline":
            return []

    try:
        items = search_items(geometry_json, start_date, end_date)
        ranked = rank_candidates(items, geometry)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Sentinel Earth Search query failed for {year}: {exc}")
        return []

    observations = []
    for candidate in ranked[:count]:
        try:
            arrays, metadata = read_scene(candidate.item, geometry)
            metadata["aoi_scl_quality"] = {
                "valid_fraction": candidate.valid_fraction,
                "strict_valid_fraction": candidate.strict_valid_fraction,
                "low_confidence_fraction": candidate.low_confidence_fraction,
            }
            metadata["request_hash"] = request_hash
            metadata["acquisition_mode"] = "online_stac"
            saved = cache.put(candidate.item.id, arrays, metadata)
            observations.append(_observation_from_cached(arrays, saved))
        except Exception as exc:  # noqa: BLE001
            warnings.append(
                f"Sentinel online scene {getattr(candidate.item, 'id', '?')} failed: {exc}"
            )
    return sorted(observations, key=lambda item: item.observed_on)


def _observations_for_mode(
    scene_rows,
    aoi_id: str,
    year: int,
    geometry,
    dataset_root: Path,
    *,
    mode: str,
    warnings: list[str],
) -> list[SceneObservation]:
    if mode != "online":
        local = _load_observations(scene_rows, aoi_id, year, geometry, dataset_root)
        if local:
            return local
    if mode == "offline":
        return _stac_observations(
            geometry, year, mode="offline", warnings=warnings
        )
    return _stac_observations(
        geometry,
        year,
        mode="online" if mode == "online" else "auto",
        warnings=warnings,
    )


def _evidence_from_dict(payload: dict) -> Evidence:
    return Evidence(
        payload["family"],
        payload.get("strength", "partial"),
        payload.get("direction", "unknown"),
        payload.get("date_min"),
        payload.get("date_max"),
        bool(payload.get("supports_fire", False)),
        payload.get("note"),
    )


def _event_carbon(
    geom_wgs84,
    start_clip,
    end_clip,
    aoi_area_ha: float,
    total_abs_signal_t: float,
):
    if (
        start_clip.agb.shape != end_clip.agb.shape
        or tuple(start_clip.transform) != tuple(end_clip.transform)
    ):
        return None
    contribution = event_emission_contribution(
        geom_wgs84, start_clip.agb, end_clip.agb, start_clip.transform
    )
    contribution["share_of_aoi_area"] = (
        contribution["area_ha"] / aoi_area_ha if aoi_area_ha > 0 else None
    )
    contribution["share_of_absolute_carbon_change_signal"] = (
        contribution["absolute_carbon_change_signal_t"] / total_abs_signal_t
        if total_abs_signal_t > 0
        else None
    )
    return contribution


def _build_events(
    dataset: LocalDataset,
    parent_parts,
    request: AnalysisRequest,
    parent_year_inputs: dict,
    warnings: list[str],
) -> tuple[list[dict], list[dict]]:
    try:
        scene_rows = load_scene_rows(dataset.root)
    except Exception as exc:
        scene_rows = []
        warnings.append(f"Local Sentinel scene index unavailable: {exc}")
        if request.data_mode == "offline":
            return [], []

    events: list[dict] = []
    layers: list[dict] = []
    for parent, part_geom in parent_parts:
        start_key = (parent.aoi_id, request.year_start)
        end_key = (parent.aoi_id, request.year_end)
        start_clip = parent_year_inputs.get(start_key, (None, None, None))[0]
        end_clip = parent_year_inputs.get(end_key, (None, None, None))[0]
        total_abs_signal = 0.0
        if (
            start_clip is not None
            and end_clip is not None
            and start_clip.agb.shape == end_clip.agb.shape
            and tuple(start_clip.transform) == tuple(end_clip.transform)
        ):
            weights = area_weight_grid(start_clip, part_geom)
            valid = (
                np.isfinite(start_clip.agb)
                & np.isfinite(end_clip.agb)
                & np.isfinite(weights)
                & (weights > 0)
            )
            total_abs_signal = float(
                np.sum(
                    weights[valid]
                    * np.abs(end_clip.agb[valid] - start_clip.agb[valid])
                    * CF
                )
            )

        for year in range(request.year_start, request.year_end):
            before_obs = _observations_for_mode(
                scene_rows,
                parent.aoi_id,
                year,
                part_geom,
                dataset.root,
                mode=request.data_mode,
                warnings=warnings,
            )
            after_obs = _observations_for_mode(
                scene_rows,
                parent.aoi_id,
                year + 1,
                part_geom,
                dataset.root,
                mode=request.data_mode,
                warnings=warnings,
            )
            if not before_obs or not after_obs:
                continue
            try:
                detected = detect_transition(before_obs, after_obs)
            except Exception as exc:
                warnings.append(
                    f"Change transition {parent.aoi_id} {year}->{year+1} failed: {exc}"
                )
                continue

            diagnostic_obs = (
                _load_observations(
                    scene_rows,
                    parent.aoi_id,
                    year,
                    part_geom,
                    dataset.root,
                    months=frozenset({9, 10}),
                )
                if request.data_mode != "online"
                else []
            )

            layers.append(
                {
                    "id": f"sentinel-change-{parent.aoi_id}-{year}-{year+1}",
                    "family": "sentinel2",
                    "type": "change_objects",
                    "transition": [year, year + 1],
                    "crs": detected["crs"],
                    "quality": detected["quality"],
                }
            )

            for direction, objects in (
                ("disturbance", detected["loss_objects"]),
                ("recovery", detected["gain_objects"]),
            ):
                for idx, obj in enumerate(objects, 1):
                    diagnostic_quality = []
                    supported_dates = []
                    for diagnostic_scene in diagnostic_obs:
                        diagnostic = diagnostic_post_signal(
                            obj,
                            detected["before_composite"],
                            diagnostic_scene,
                            reference_transform=before_obs[0].transform,
                            reference_crs=before_obs[0].crs,
                            direction=direction,
                        )
                        meta = diagnostic_scene.metadata or {}
                        scene_quality = diagnostic.pop("scene_quality", {})
                        diagnostic_quality.append({
                            "stage": "diagnostic",
                            "date": diagnostic_scene.observed_on.isoformat(),
                            **scene_quality,
                            **diagnostic,
                            "scene_id": meta.get("scene_id") or meta.get("item_id"),
                            "processing_baseline": meta.get("processing_baseline")
                            or meta.get("s2:processing_baseline")
                            or meta.get("processing:version"),
                            "radiometry": meta.get("radiometry")
                            or meta.get("scale_offset")
                            or meta.get("bands"),
                            "reflectance_path": meta.get("reflectance_path"),
                            "scl_path": meta.get("scl_path"),
                            "used_for_annual_composite": False,
                        })
                        if diagnostic.get("supports_post_change"):
                            supported_dates.append(diagnostic_scene.observed_on)
                    post_override = min(supported_dates) if supported_dates else None
                    geom_wgs84, s2_ev = sentinel_evidence(
                        obj,
                        before_obs,
                        after_obs,
                        direction=direction,
                        post_date_override=post_override,
                    )
                    ev_objects = [s2_ev]
                    details = [
                        {
                            "family": "sentinel2",
                            "strength": "strong",
                            "direction": s2_ev.direction,
                            "date_min": s2_ev.date_min.isoformat() if s2_ev.date_min else None,
                            "date_max": s2_ev.date_max.isoformat() if s2_ev.date_max else None,
                            "note": (
                                "Robust annual NDVI/NBR/NDMI agreement; "
                                + (
                                    "date_max tightened by diagnostic-only post-event scene."
                                    if post_override
                                    else "no diagnostic-only scene passed the post-change support rule."
                                )
                            ),
                        }
                    ]

                    if direction == "disturbance":
                        for candidate_year in (year, year + 1):
                            gfc = gfc_event_evidence(
                                dataset.root, parent.aoi_id, geom_wgs84, candidate_year
                            )
                            if gfc:
                                ev_objects.append(_evidence_from_dict(gfc))
                                details.append(
                                    {
                                        **{
                                            k: (
                                                v.isoformat()
                                                if hasattr(v, "isoformat")
                                                else v
                                            )
                                            for k, v in gfc.items()
                                            if k not in {"path"}
                                        },
                                        "source_path": gfc.get("path"),
                                        "note": "GFC is loss evidence, not cause or biomass amount.",
                                    }
                                )
                                break
                        for candidate_year in (year, year + 1):
                            modis = modis_fire_evidence(
                                dataset.root, parent.aoi_id, geom_wgs84, candidate_year
                            )
                            if modis:
                                ev_objects.append(_evidence_from_dict(modis))
                                details.append(
                                    {
                                        **{
                                            k: (
                                                v.isoformat()
                                                if hasattr(v, "isoformat")
                                                else v
                                            )
                                            for k, v in modis.items()
                                            if k not in {"burn_path", "qa_path"}
                                        },
                                        "source_paths": [
                                            modis.get("burn_path"),
                                            modis.get("qa_path"),
                                        ],
                                        "note": "MODIS 500 m pixels support fire timing/cause, not exact burn geometry.",
                                    }
                                )
                                break

                    carbon = None
                    event_limitations = []
                    if start_clip is not None and end_clip is not None:
                        carbon = _event_carbon(
                            geom_wgs84,
                            start_clip,
                            end_clip,
                            geodesic_area_ha(part_geom),
                            total_abs_signal,
                        )
                        if carbon is not None:
                            cdir = "loss" if carbon["E_event_tco2e"] > 0 else "gain"
                            expected = (
                                "loss" if direction == "disturbance" else "gain"
                            )
                            if (
                                cdir == expected
                                and abs(carbon["E_event_tco2e"]) > 0
                            ):
                                ev_objects.append(Evidence("cci", "partial", cdir))
                                details.append(
                                    {
                                        "family": "cci",
                                        "strength": "partial",
                                        "direction": cdir,
                                        "note": "CCI request-period stock signal overlaps the event geometry.",
                                    }
                                )
                        else:
                            event_limitations.append(
                                "Event carbon contribution unavailable because start/end CCI grids do not align."
                            )
                    else:
                        event_limitations.append(
                            "Event carbon contribution unavailable because request-period CCI inputs are missing."
                        )

                    event_id = (
                        f"{parent.aoi_id}-{year}-{year+1}-{direction}-{idx:03d}"
                    )
                    events.append(
                        fused_event_record(
                            event_id=event_id,
                            geometry_wgs84=geom_wgs84,
                            area_ha=obj.area_ha,
                            direction=direction,
                            evidence=ev_objects,
                            evidence_details=details,
                            data_quality=[
                                {"stage": "before", **q}
                                for q in detected["quality"]["before"]
                            ]
                            + [
                                {"stage": "after", **q}
                                for q in detected["quality"]["after"]
                            ]
                            + diagnostic_quality,
                            carbon_contribution=carbon,
                            limitations=event_limitations
                            + [
                                "Event E is contribution to the observed stock-change signal, not automatic causal attribution."
                            ],
                        )
                    )
    return events, layers


def _price_scenarios(q: int | None) -> list[dict]:
    if q is None:
        return []
    return [
        {
            "label": "1000 RUB/tCO2e",
            "price_rub_per_unit": 1000,
            "gross_value_rub": q * 1000,
        },
        {
            "label": "3000 RUB/tCO2e",
            "price_rub_per_unit": 3000,
            "gross_value_rub": q * 3000,
        },
        {
            "label": "5000 RUB/tCO2e",
            "price_rub_per_unit": 5000,
            "gross_value_rub": q * 5000,
        },
    ]


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
    official_metadata = load_official_metadata(dataset.root)
    parent_parts = dataset.intersecting_parents(geom)
    if request.parent_aoi_id:
        parent_parts = [
            (p, g) for p, g in parent_parts if p.aoi_id == request.parent_aoi_id
        ]
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
            yearly.append(
                {
                    "year": year,
                    "area_ha": total.area_ha,
                    "total_carbon_t": total.total_carbon_t,
                    "mean_carbon_t_ha": total.mean_carbon_t_ha,
                }
            )

    yearly.sort(key=lambda p: p["year"])
    if yearly:
        first_total = float(yearly[0]["total_carbon_t"])
        previous_total = None
        for point in yearly:
            total = float(point["total_carbon_t"])
            annual_delta = None if previous_total is None else total - previous_total
            cumulative_delta = total - first_total
            point["annual_delta_c_t"] = annual_delta
            point["annual_E_tco2e"] = (
                None if annual_delta is None else -annual_delta * CO2_PER_C
            )
            point["cumulative_delta_c_t"] = cumulative_delta
            point["cumulative_E_tco2e"] = -cumulative_delta * CO2_PER_C
            previous_total = total

    if request.year_start not in stock_by_year or request.year_end not in stock_by_year:
        raise ValueError("Required CCI start/end year data are unavailable")

    start = stock_by_year[request.year_start]
    end = stock_by_year[request.year_end]
    computed_area = min(start.area_ha, end.area_ha)
    cov = coverage_result(requested_area, computed_area)
    E = stock_difference_emission_tco2e(start, end)
    e = annualized_emission_intensity(
        E, computed_area, request.year_start, request.year_end
    )

    temporal_diagnostics = []
    for parent, part_geom in parent_parts:
        try:
            diagnostic = temporal_rho_from_official_change(
                dataset.root, parent.aoi_id, part_geom
            )
            if diagnostic is not None:
                temporal_diagnostics.append({"aoi_id": parent.aoi_id, **diagnostic})
        except ValueError as exc:
            temporal_diagnostics.append({
                "aoi_id": parent.aoi_id,
                "status": "unavailable",
                "reason": str(exc),
            })

    uncertainty_scenarios = ("independent", "moderate", "strong")
    scenario_parts: dict[str, list[tuple[str, Any]]] = {
        name: [] for name in uncertainty_scenarios
    }
    for parent, part_geom in parent_parts:
        key0 = (parent.aoi_id, request.year_start)
        key1 = (parent.aoi_id, request.year_end)
        if key0 not in parent_year_inputs or key1 not in parent_year_inputs:
            continue
        c0, _, _ = parent_year_inputs[key0]
        c1, _, _ = parent_year_inputs[key1]
        if (
            c0.agb.shape != c1.agb.shape
            or tuple(c0.transform) != tuple(c1.transform)
        ):
            continue
        weights = area_weight_grid(c0, part_geom)
        for scenario_name in uncertainty_scenarios:
            try:
                u = run_scenario(
                    scenario_name,
                    agb0=c0.agb,
                    agb1=c1.agb,
                    sd0=c0.sd,
                    sd1=c1.sd,
                    area_ha=weights,
                    simulations=simulations,
                    seed=seed,
                )
                scenario_parts[scenario_name].append((parent.aoi_id, u))
            except ValueError:
                continue

    scenario_bounds: dict[str, tuple[float, float]] = {}
    for scenario_name, parts in scenario_parts.items():
        if len(parts) != len(parent_parts):
            continue
        scenario_bounds[scenario_name] = (
            sum(u.lower_tco2e for _, u in parts),
            sum(u.upper_tco2e for _, u in parts),
        )

    selected_parts = scenario_parts.get(request.uncertainty_scenario, [])
    selected_bounds = scenario_bounds.get(request.uncertainty_scenario)
    if selected_bounds is not None:
        lower, upper = selected_bounds
        uncertainty = {
            "L": lower,
            "U": upper,
            "method": "sum of parent-part model-based correlated Monte Carlo intervals",
            "assumptions": {
                "scenario": request.uncertainty_scenario,
                "simulations": simulations,
                "seed": seed,
                "cross_parent_aggregation": "conservative bound summation",
                "parts": [
                    {"aoi_id": aoi, **asdict(u)} for aoi, u in selected_parts
                ],
                "temporal_diagnostic_2019_2020": temporal_diagnostics,
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
            baseline_proof.append(
                {
                    "aoi_id": parent.aoi_id,
                    "area_ha": area,
                    "cbar_2015": trajectory.cbar_2015_tC_ha,
                    "cbar_2019": trajectory.cbar_2019_tC_ha,
                }
            )

    baseline_available = len(baseline_parts) == len(parent_parts)
    Ebase = (
        aggregate_baseline(
            baseline_parts, request.year_start, request.year_end
        )
        if baseline_available
        else None
    )

    credits_obj = calculate_potential_credits(
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
    credits = asdict(credits_obj)
    credits["scenario_values_rub"] = _price_scenarios(credits_obj.Q)
    credits["price_scenario_disclaimer"] = (
        "Illustrative gross-value scenarios only; not a market-price forecast."
    )

    if uncertainty is not None:
        sensitivity_rows = []
        for scenario_name in uncertainty_scenarios:
            bounds = scenario_bounds.get(scenario_name)
            if bounds is None:
                sensitivity_rows.append({
                    "scenario": scenario_name,
                    "status": "unavailable",
                    "reason": "incomplete_uncertainty_inputs",
                })
                continue
            scenario_lower, scenario_upper = bounds
            scenario_credits = calculate_potential_credits(
                area_ha=computed_area,
                year_start=request.year_start,
                year_end=request.year_end,
                Ebase=Ebase,
                Eproj=E,
                lower=scenario_lower,
                upper=scenario_upper,
                full_coverage=cov.reason is None,
                baseline_available=baseline_available,
            )
            sensitivity_rows.append({
                "scenario": scenario_name,
                "status": scenario_credits.status,
                "L": scenario_lower,
                "U": scenario_upper,
                "interval_width_tco2e": scenario_upper - scenario_lower,
                "H": scenario_credits.H,
                "H_over_R": scenario_credits.H_over_R,
                "UNC": scenario_credits.UNC,
                "Q": scenario_credits.Q,
            })
        uncertainty["sensitivity"] = sensitivity_rows

    warnings = [cov.reason] if cov.reason else []
    events, layers = _build_events(
        dataset, parent_parts, request, parent_year_inputs, warnings
    )

    config_material = {
        "request": request.model_dump(),
        "simulations": simulations,
        "seed": seed,
        "uncertainty_scenario": request.uncertainty_scenario,
    }

    return {
        "status": "completed",
        "request": {
            **request.model_dump(),
            "requested_area_ha": requested_area,
        },
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
        "events": events,
        "layers": layers,
        "baseline": {
            "Ebase": Ebase,
            "parent_parts": baseline_proof,
            "available": baseline_available,
        },
        "credits": credits,
        "provenance": {
            "sources": [
                "ESA CCI Biomass v7.0",
                "official methodology/baseline.csv",
                "Sentinel-2 L2A prepared scenes when available",
                "GFC/MODIS evidence when available",
            ],
            "checksums": provenance_files,
            "processing_config_hash": canonical_json_hash(config_material),
            "random_seed": seed,
            "uncertainty_scenario": request.uncertainty_scenario,
            "official_metadata": compact_metadata_provenance(official_metadata),
        },
        "limitations": LIMITATIONS
        + [
            "Missing external evidence reduces event confidence instead of being silently inferred."
        ],
        "warnings": warnings,
    }
