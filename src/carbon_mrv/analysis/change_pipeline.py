from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from carbon_mrv.change.composites import robust_annual_composite
from carbon_mrv.change.fusion import Evidence, fuse_event
from carbon_mrv.change.indices import scene_indices
from carbon_mrv.change.objects import connected_objects
from carbon_mrv.change.transitions import transition_maps
from carbon_mrv.geometry.reproject import reproject_geometry
from carbon_mrv.quality.scl import scl_quality_summary, scl_valid_mask


@dataclass(frozen=True)
class SceneObservation:
    observed_on: date
    bands: dict[str, np.ndarray]
    scl: np.ndarray
    transform: object
    crs: str = "EPSG:4326"
    metadata: dict | None = None


def annual_from_scenes(scenes: list[SceneObservation]):
    if not scenes:
        raise ValueError("At least one scene is required")
    first_shape = next(iter(scenes[0].bands.values())).shape
    for scene in scenes:
        if next(iter(scene.bands.values())).shape != first_shape:
            raise ValueError("Annual scenes must share a common grid")
        if tuple(scene.transform) != tuple(scenes[0].transform) or scene.crs != scenes[0].crs:
            raise ValueError("Annual scenes must share transform and CRS")
    index_scenes, masks, quality = [], [], []
    for scene in scenes:
        mask = scl_valid_mask(scene.scl, allow_low_confidence=True)
        index_scenes.append(scene_indices(scene.bands))
        masks.append(mask)
        meta = scene.metadata or {}
        quality.append({
            "date": scene.observed_on.isoformat(),
            **scl_quality_summary(scene.scl),
            "scene_id": meta.get("scene_id") or meta.get("item_id") or meta.get("id"),
            "processing_baseline": meta.get("processing_baseline")
            or meta.get("s2:processing_baseline")
            or meta.get("processing:version"),
            "radiometry": meta.get("radiometry")
            or meta.get("scale_offset")
            or meta.get("bands"),
        })
    return robust_annual_composite(index_scenes, masks), quality


def detect_transition(
    before_scenes: list[SceneObservation],
    after_scenes: list[SceneObservation],
    *,
    z_threshold: float = 2.5,
    min_index_agreement: int = 2,
    min_area_ha: float = 0.25,
    min_observations: int = 1,
):
    before, qa_before = annual_from_scenes(before_scenes)
    after, qa_after = annual_from_scenes(after_scenes)
    transition = transition_maps(
        before,
        after,
        z_threshold=z_threshold,
        min_index_agreement=min_index_agreement,
        min_observations=min_observations,
    )
    transform = before_scenes[0].transform
    loss_objects = connected_objects(
        transition.disturbance, transition.score, transform,
        crs=before_scenes[0].crs, min_area_ha=min_area_ha
    )
    gain_objects = connected_objects(
        transition.recovery, -transition.score, transform,
        crs=before_scenes[0].crs, min_area_ha=min_area_ha
    )
    return {
        "transition": transition,
        "loss_objects": loss_objects,
        "gain_objects": gain_objects,
        "quality": {"before": qa_before, "after": qa_after},
        "crs": before_scenes[0].crs,
    }


def sentinel_evidence(
    obj,
    before_scenes: list[SceneObservation],
    after_scenes: list[SceneObservation],
    *,
    direction: str,
):
    last_pre = max(s.observed_on for s in before_scenes)
    first_post = min(s.observed_on for s in after_scenes)
    geom_wgs84 = reproject_geometry(obj.geometry, before_scenes[0].crs, "EPSG:4326")
    evidence = Evidence(
        "sentinel2",
        "strong",
        "loss" if direction == "disturbance" else "gain",
        last_pre,
        first_post,
    )
    return geom_wgs84, evidence


def fused_event_record(
    *,
    event_id: str,
    geometry_wgs84,
    area_ha: float,
    direction: str,
    evidence: list[Evidence],
    evidence_details: list[dict],
    data_quality: list[dict],
    carbon_contribution: dict | None = None,
    limitations: list[str] | None = None,
):
    fusion = fuse_event(evidence)
    return {
        "event_id": event_id,
        "geometry": geometry_wgs84.__geo_interface__,
        "area_ha": area_ha,
        "direction": direction,
        **fusion,
        "evidence": evidence_details,
        "data_quality": data_quality,
        "carbon_contribution": carbon_contribution,
        "limitations": limitations or [],
    }
