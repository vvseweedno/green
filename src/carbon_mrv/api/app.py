from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from carbon_mrv.analysis.pipeline import analyze_local
from carbon_mrv.domain.models import AnalysisRequest
from carbon_mrv.reporting.report import write_report

app = FastAPI(title="Carbon MRV API", version="0.1.0")
RUNS = Path(os.getenv("CARBON_MRV_RUNS", "runs"))
DATASET = Path(os.getenv("CARBON_MRV_DATASET", "data/raw"))
RUNS.mkdir(parents=True, exist_ok=True)


def _run_path(run_id: str) -> Path:
    return RUNS / f"{run_id}.json"


def _load(run_id: str):
    path = _run_path(run_id)
    if not path.exists():
        raise HTTPException(404, "run not found")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/health")
def health():
    return {"status": "ok", "dataset_exists": DATASET.exists()}


@app.post("/api/v1/analysis")
def create_analysis(request: AnalysisRequest):
    run_id = str(uuid4())
    try:
        result = analyze_local(request, DATASET)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(422, str(exc)) from exc
    result["run_id"] = run_id
    _run_path(run_id).write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    write_report(result, RUNS)
    return result


@app.get("/api/v1/analysis/{run_id}")
def get_analysis(run_id: str):
    return _load(run_id)


@app.get("/api/v1/analysis/{run_id}/layers")
def get_layers(run_id: str):
    result = _load(run_id)
    return {"run_id": run_id, "layers": result.get("layers", []), "events": result.get("events", [])}


@app.get("/api/v1/analysis/{run_id}/events")
def get_events(run_id: str):
    return {"run_id": run_id, "events": _load(run_id).get("events", [])}


@app.get("/api/v1/analysis/{run_id}/provenance")
def get_provenance(run_id: str):
    return {"run_id": run_id, "provenance": _load(run_id).get("provenance", {})}


@app.get("/api/v1/analysis/{run_id}/report")
def get_report(run_id: str):
    _load(run_id)
    path = RUNS / f"{run_id}.html"
    if not path.exists():
        raise HTTPException(404, "report not found")
    return FileResponse(path, media_type="text/html", filename=path.name)
