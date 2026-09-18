from datetime import date

import numpy as np
from affine import Affine
from shapely.geometry import box

from carbon_mrv.analysis.change_pipeline import SceneObservation, diagnostic_post_signal
from carbon_mrv.change.objects import ChangeObject


def _scene(scl_value: int) -> SceneObservation:
    shape=(10,10)
    b8a=np.full(shape,0.8,dtype=float)
    b04=np.full(shape,0.2,dtype=float)
    b11=np.full(shape,0.2,dtype=float)
    b12=np.full(shape,0.2,dtype=float)
    # Event footprint rows 2:5, cols 2:5 becomes strongly non-vegetated / burned-looking.
    for arr in (b04,b11,b12):
        arr[2:5,2:5]=0.8
    b8a[2:5,2:5]=0.2
    scl=np.full(shape,4,dtype=np.uint8)
    if scl_value != 4:
        scl[2:5,2:5]=scl_value
    return SceneObservation(
        date(2021,9,12),
        {"B02":np.zeros(shape),"B03":np.zeros(shape),"B04":b04,"B8A":b8a,"B11":b11,"B12":b12},
        scl,
        Affine(1,0,0,0,-1,10),
        "EPSG:4326",
        {"scene_id":"diag"},
    )


def _before():
    shape=(10,10)
    value=np.full(shape,0.6,dtype=float)
    return {"NBR":value.copy(),"NDVI":value.copy(),"NDMI":value.copy()}


def _object():
    # Under transform y=10-row, rows 2:5 / cols 2:5 correspond roughly x 2..5, y 5..8.
    return ChangeObject("x",box(2,5,5,8),9.0,9,10.0)


def test_diagnostic_scene_tightens_only_on_multi_index_valid_support():
    scene=_scene(4)
    out=diagnostic_post_signal(
        _object(),_before(),scene,
        reference_transform=scene.transform,reference_crs=scene.crs,
        direction="disturbance",
    )
    assert out["supports_post_change"] is True
    assert out["index_agreement"] >= 2
    assert out["event_valid_fraction"] == 1.0
    assert out["used_for_annual_composite"] is False


def test_diagnostic_scene_rejected_when_event_pixels_are_invalid_scl():
    scene=_scene(9)
    out=diagnostic_post_signal(
        _object(),_before(),scene,
        reference_transform=scene.transform,reference_crs=scene.crs,
        direction="disturbance",
    )
    assert out["supports_post_change"] is False
    assert out["reason"]=="insufficient_valid_event_observations"
    assert out["event_valid_fraction"] == 0.0
