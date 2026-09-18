#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from carbon_mrv.analysis.pipeline import analyze_local
from carbon_mrv.data.local import LocalDataset
from carbon_mrv.domain.models import AnalysisRequest
from carbon_mrv.reporting.report import write_report


def _years(props: dict) -> tuple[int, int]:
    y0=props.get("year_start") or props.get("start_year") or props.get("t0")
    y1=props.get("year_end") or props.get("end_year") or props.get("t1")
    if y0 is None or y1 is None:
        raise ValueError("sample request missing start/end years")
    return int(y0),int(y1)


def _save(name: str, req: AnalysisRequest, dataset: Path, runs: Path) -> dict:
    result=analyze_local(req,dataset,simulations=300,seed=20260918)
    result["run_id"]=name
    result["created_at_utc"]=datetime.now(timezone.utc).isoformat()
    html_path,json_path=write_report(result,runs,dataset)
    return {
        "run_id":name,
        "html":str(html_path),
        "json":str(json_path),
        "coverage_ratio":result["coverage"]["coverage_ratio"],
        "E_tco2e":result["stock"]["E_tco2e"],
        "Q":result["credits"].get("Q"),
        "credits_status":result["credits"].get("status"),
        "event_count":len(result.get("events",[])),
    }


def main():
    ap=argparse.ArgumentParser(description="Generate the deterministic jury demo suite")
    ap.add_argument("--dataset",default="data/raw")
    ap.add_argument("--runs",default="runs/demo")
    args=ap.parse_args()
    dataset=Path(args.dataset)
    runs=Path(args.runs)
    if not dataset.exists():
        raise SystemExit("Official dataset unavailable; demo outputs are not fabricated")
    ds=LocalDataset(dataset)
    parents={p.aoi_id:p for p in ds.parent_aois()}
    outputs=[]
    for aoi_id,name in (("RU_MORDOVIA_03","demo_changed"),("RU_TVER_01","demo_control")):
        if aoi_id not in parents:
            raise RuntimeError(f"required demo AOI missing: {aoi_id}")
        outputs.append(_save(
            name,
            AnalysisRequest(
                geometry=parents[aoi_id].geometry.__geo_interface__,
                year_start=2020,year_end=2022,data_mode="offline",
                parent_aoi_id=aoi_id,uncertainty_scenario="moderate",
            ),
            dataset,runs,
        ))

    sample=json.loads(ds.require("sample_requests.geojson").read_text(encoding="utf-8"))
    target=None
    for feature in sample.get("features",[]):
        props=feature.get("properties") or {}
        fid=props.get("request_id") or props.get("id") or props.get("name") or feature.get("id")
        if str(fid)=="CHECK_TRANSFER_01":
            target=feature;break
    if target is None:
        raise RuntimeError("CHECK_TRANSFER_01 not found in sample_requests.geojson")
    y0,y1=_years(target.get("properties") or {})
    outputs.append(_save(
        "demo_transfer_CHECK_TRANSFER_01",
        AnalysisRequest(
            geometry=target["geometry"],year_start=y0,year_end=y1,
            data_mode="offline",uncertainty_scenario="moderate",
        ),
        dataset,runs,
    ))
    manifest=runs/"manifest.json"
    manifest.write_text(json.dumps(outputs,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"ok":True,"manifest":str(manifest),"runs":outputs},indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
