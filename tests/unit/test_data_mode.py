from datetime import date

import numpy as np
from affine import Affine

import carbon_mrv.analysis.pipeline as pipeline
from carbon_mrv.analysis.change_pipeline import SceneObservation


def _obs(tag: str):
    shape=(1,1)
    return SceneObservation(
        date(2021,7,1),
        {name:np.ones(shape,dtype=float) for name in ("B02","B03","B04","B8A","B11","B12")},
        np.full(shape,4,dtype=np.uint8),
        Affine.identity(),
        "EPSG:4326",
        {"scene_id":tag},
    )


def test_auto_prefers_local_and_does_not_call_stac(monkeypatch,tmp_path):
    local=[_obs("local")]
    monkeypatch.setattr(pipeline,"_load_observations",lambda *a,**k:local)
    def fail(*a,**k):
        raise AssertionError("STAC should not be called when local data exists")
    monkeypatch.setattr(pipeline,"_stac_observations",fail)
    out=pipeline._observations_for_mode([], "A", 2021, None, tmp_path, mode="auto", warnings=[])
    assert out[0].metadata["scene_id"]=="local"


def test_online_bypasses_local_and_forces_stac(monkeypatch,tmp_path):
    def fail_local(*a,**k):
        raise AssertionError("online mode must bypass prepared local scenes")
    monkeypatch.setattr(pipeline,"_load_observations",fail_local)
    calls=[]
    monkeypatch.setattr(
        pipeline,"_stac_observations",
        lambda *a,**k:(calls.append(k["mode"]) or [_obs("online")]),
    )
    out=pipeline._observations_for_mode([], "A", 2021, None, tmp_path, mode="online", warnings=[])
    assert calls==["online"]
    assert out[0].metadata["scene_id"]=="online"


def test_offline_uses_cache_path_when_local_is_missing(monkeypatch,tmp_path):
    monkeypatch.setattr(pipeline,"_load_observations",lambda *a,**k:[])
    calls=[]
    monkeypatch.setattr(
        pipeline,"_stac_observations",
        lambda *a,**k:(calls.append(k["mode"]) or [_obs("cache")]),
    )
    out=pipeline._observations_for_mode([], "A", 2021, None, tmp_path, mode="offline", warnings=[])
    assert calls==["offline"]
    assert out[0].metadata["scene_id"]=="cache"
