from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from carbon_mrv.change.composites import robust_annual_composite
from carbon_mrv.change.fusion import Evidence, fuse_event
from carbon_mrv.change.indices import scene_indices
from carbon_mrv.change.objects import connected_objects
from carbon_mrv.change.transitions import transition_maps
from carbon_mrv.quality.scl import scl_quality_summary, scl_valid_mask


@dataclass(frozen=True)
class SceneObservation:
    observed_on: date
    bands: dict[str, np.ndarray]
    scl: np.ndarray
    transform: object


def annual_from_scenes(scenes: list[SceneObservation]):
    if not scenes:
        raise ValueError("At least one scene is required")
    index_scenes, masks, quality = [], [], []
    for scene in scenes:
        mask = scl_valid_mask(scene.scl, allow_low_confidence=True)
        index_scenes.append(scene_indices(scene.bands))
        masks.append(mask)
        quality.append({"date": scene.observed_on.isoformat(), **scl_quality_summary(scene.scl)})
    return robust_annual_composite(index_scenes, masks), quality


def detect_transition(
    before_scenes: list[SceneObservation],
    after_scenes: list[SceneObservation],
    *,
    z_threshold: float = 2.5,
    min_index_agreement: int = 2,
    min_area_ha: float = 0.25,
):
    before, qa_before = annual_from_scenes(before_scenes)
    after, qa_after = annual_from_scenes(after_scenes)
    transition = transition_maps(
        before,
        after,
        z_threshold=z_threshold,
        min_index_agreement=min_index_agreement,
    )
    transform = before_scenes[0].transform
    loss_objects = connected_objects(
        transition.disturbance, transition.score, transform, min_area_ha=min_area_ha
    )
    gain_objects = connected_objects(
        transition.recovery, -transition.score, transform, min_area_ha=min_area_ha
    )
    return {
        "transition": transition,
        "loss_objects": loss_objects,
        "gain_objects": gain_objects,
        "quality": {"before": qa_before, "after": qa_after},
    }


def sentinel_event_record(
    obj,
    before_scenes: list[SceneObservation],
    after_scenes: list[SceneObservation],
    *,
    direction: str,
):
    last_pre = max(s.observed_on for s in before_scenes)
    first_post = min(s.observed_on for s in after_scenes)
    evidence = [
        Evidence(
            "sentinel2",
            "strong",
            "loss" if direction == "disturbance" else "gain",
            last_pre,
            first_post,
        )
    ]
    fusion = fuse_event(evidence)
    return {
        "event_id": obj.object_id,
        "geometry": obj.geometry.__geo_interface__,
        "area_ha": obj.area_ha,
        "direction": direction,
        **fusion,
        "evidence": [{
            "family": "sentinel2",
            "strength": "strong",
            "date_min": last_pre.isoformat(),
            "date_max": first_post.isoformat(),
        }],
        "data_quality": [],
        "limitations": ["Cause is not established from optical change alone."],
    }
