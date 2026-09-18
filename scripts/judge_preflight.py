#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from carbon_mrv.analysis.pipeline import analyze_local
from carbon_mrv.data.local import LocalDataset
from carbon_mrv.data.provenance import canonical_json_hash
from carbon_mrv.domain.models import AnalysisRequest
from carbon_mrv.reporting.report import write_report

DATASET = Path(os.getenv("CARBON_MRV_DATASET", "data/raw"))
RUNS = Path(os.getenv("CARBON_MRV_RUNS", "runs/judge"))


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def _properties_years(props: dict) -> tuple[int, int]:
    y0 = props.get("year_start") or props.get("start_year") or props.get("t0")
    y1 = props.get("year_end") or props.get("end_year") or props.get("t1")
    if y0 is None or y1 is None:
        raise ValueError("sample request must expose year_start/year_end (or start_year/end_year, t0/t1)")
    return int(y0), int(y1)


def _case(name: str, geometry: dict, y0: int, y1: int, parent: str | None = None):
    req = AnalysisRequest(
        geometry=geometry,
        year_start=y0,
        year_end=y1,
        data_mode="offline",
        parent_aoi_id=parent,
        uncertainty_scenario="moderate",
    )
    first = analyze_local(req, DATASET, simulations=300, seed=20260918)
    second = analyze_local(req, DATASET, simulations=300, seed=20260918)
    h1 = canonical_json_hash(first)
    h2 = canonical_json_hash(second)
    if h1 != h2:
        raise RuntimeError(f"non-deterministic replay for {name}: {h1} != {h2}")
    payload = {**first, "run_id": name}
    html_path, json_path = write_report(payload, RUNS)
    if not html_path.exists() or not json_path.exists():
        raise RuntimeError(f"report generation failed for {name}")
    print(json.dumps({
        "case": name,
        "result_hash": h1,
        "Q": first["credits"].get("Q"),
        "events": len(first.get("events", [])),
        "report": str(html_path),
    }, ensure_ascii=False))


def main() -> int:
    run([sys.executable, "-m", "pytest", "-q"])
    if not DATASET.exists():
        print("JUDGE PREFLIGHT BLOCKED: official dataset is missing. Unit tests passed; real-data evidence cannot be fabricated.")
        return 2
    run([sys.executable, "scripts/verify_dataset.py", str(DATASET)])
    ds = LocalDataset(DATASET)
    parents = {p.aoi_id: p for p in ds.parent_aois()}
    for aoi_id, name in (("RU_MORDOVIA_03", "judge_changed"), ("RU_TVER_01", "judge_control")):
        if aoi_id not in parents:
            raise RuntimeError(f"required judge AOI missing: {aoi_id}")
        _case(name, parents[aoi_id].geometry.__geo_interface__, 2020, 2022, aoi_id)

    sample_path = ds.require("sample_requests.geojson")
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    target = None
    for feature in payload.get("features", []):
        props = feature.get("properties") or {}
        fid = props.get("request_id") or props.get("id") or props.get("name") or feature.get("id")
        if str(fid) == "CHECK_TRANSFER_01":
            target = feature
            break
    if target is None:
        raise RuntimeError("CHECK_TRANSFER_01 not found in sample_requests.geojson")
    y0, y1 = _properties_years(target.get("properties") or {})
    _case("judge_transfer_CHECK_TRANSFER_01", target["geometry"], y0, y1, None)

    print("JUDGE PREFLIGHT PASSED: dataset verified; changed/control/transfer cases, reports and deterministic replay passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
