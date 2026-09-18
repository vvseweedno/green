import json
import os
from pathlib import Path

import pytest

from carbon_mrv.analysis.pipeline import analyze_local
from carbon_mrv.data.local import LocalDataset
from carbon_mrv.domain.models import AnalysisRequest

ROOT = Path(os.getenv("CARBON_MRV_DATASET", "data/raw"))
pytestmark = pytest.mark.skipif(not ROOT.exists(), reason="official dataset not mounted")


def test_changed_and_control_aois_run_end_to_end():
    ds=LocalDataset(ROOT)
    parents={p.aoi_id:p for p in ds.parent_aois()}
    for aoi in ("RU_MORDOVIA_03","RU_TVER_01"):
        req=AnalysisRequest(
            geometry=parents[aoi].geometry.__geo_interface__,
            year_start=2020,year_end=2022,data_mode="offline",
            parent_aoi_id=aoi,uncertainty_scenario="moderate"
        )
        out=analyze_local(req,ROOT,simulations=30,seed=20260918)
        assert out["coverage"]["coverage_ratio"] > 0.99
        assert out["credits"]["status"] in {"available","unavailable"}
        assert "official_metadata" in out["provenance"]


def test_check_transfer_01_runs_without_code_changes():
    ds=LocalDataset(ROOT)
    payload=json.loads(ds.require("sample_requests.geojson").read_text(encoding="utf-8"))
    target=next(
        f for f in payload["features"]
        if str((f.get("properties") or {}).get("request_id")
               or (f.get("properties") or {}).get("id")
               or f.get("id"))=="CHECK_TRANSFER_01"
    )
    props=target.get("properties") or {}
    y0=int(props.get("year_start") or props.get("start_year") or props.get("t0"))
    y1=int(props.get("year_end") or props.get("end_year") or props.get("t1"))
    out=analyze_local(
        AnalysisRequest(
            geometry=target["geometry"],year_start=y0,year_end=y1,
            data_mode="offline",uncertainty_scenario="moderate"
        ),
        ROOT,simulations=30,seed=20260918
    )
    assert out["coverage"]["computed_area_ha"] > 0
