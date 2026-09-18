from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from carbon_mrv.data.provenance import sha256_file

MANDATORY_METADATA_FILES = (
    "areas.csv",
    "areas.geojson",
    "sample_requests.geojson",
    "scenes.csv",
    "scene_metadata.json",
    "events.csv",
    "sources.csv",
    "file_catalog.csv",
    "baseline.csv",
    "parameters.csv",
)


def _read_csv(path: Path) -> list[dict[str, Any]]:
    df = pd.read_csv(path)
    return df.where(pd.notna(df), None).to_dict(orient="records")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _find(root: Path, name: str) -> Path | None:
    matches = list(root.rglob(name))
    return matches[0] if matches else None


def _parameter_map(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {}
    keys = {str(k).lower(): k for k in records[0]}
    name_col = next((keys[k] for k in ("parameter", "name", "key", "parameter_name") if k in keys), None)
    value_col = next((keys[k] for k in ("value", "parameter_value", "default") if k in keys), None)
    if name_col and value_col:
        return {str(row.get(name_col)): row.get(value_col) for row in records}
    if len(records) == 1:
        return {str(k): v for k, v in records[0].items()}
    return {"records": records}


def _feature_count(payload: Any) -> int:
    if isinstance(payload, dict) and isinstance(payload.get("features"), list):
        return len(payload["features"])
    return 0


def load_official_metadata(dataset_root: str | Path) -> dict[str, Any]:
    """Read every metadata/table artifact mandated by the case."""
    root = Path(dataset_root).resolve()
    files: dict[str, Path] = {}
    missing: list[str] = []
    for name in MANDATORY_METADATA_FILES:
        path = _find(root, name)
        if path is None:
            missing.append(name)
        else:
            files[name] = path

    def csv(name: str) -> list[dict[str, Any]]:
        return _read_csv(files[name]) if name in files else []

    def js(name: str) -> Any:
        return _read_json(files[name]) if name in files else None

    areas = csv("areas.csv")
    scenes = csv("scenes.csv")
    events = csv("events.csv")
    sources = csv("sources.csv")
    parameters = csv("parameters.csv")
    sample_requests = js("sample_requests.geojson")
    scene_metadata = js("scene_metadata.json")

    return {
        "missing": missing,
        "files": {
            name: {
                "path": str(path.relative_to(root)),
                "sha256": sha256_file(path),
            }
            for name, path in files.items()
        },
        "areas_csv": areas,
        "scene_count": len(scenes),
        "scene_metadata": scene_metadata,
        "reference_events": events,
        "sources": sources,
        "methodology_parameters": _parameter_map(parameters),
        "sample_request_count": _feature_count(sample_requests),
        "sample_requests": sample_requests,
        "roles": {
            "events.csv": "reference/demo research catalog only; never detector input or cause truth",
            "sample_requests.geojson": "transferability validation inputs",
            "scene_metadata.json": "radiometry, processing-version and source-scene provenance",
            "sources.csv": "source/version provenance catalog",
            "parameters.csv": "official methodology parameter provenance and consistency checks",
            "areas.csv": "tabular AOI metadata cross-check against areas.geojson",
        },
    }


def compact_metadata_provenance(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "missing": bundle.get("missing", []),
        "files": bundle.get("files", {}),
        "area_rows": bundle.get("areas_csv", []),
        "scene_count": bundle.get("scene_count", 0),
        "sample_request_count": bundle.get("sample_request_count", 0),
        "sources": bundle.get("sources", []),
        "methodology_parameters": bundle.get("methodology_parameters", {}),
        "reference_event_count": len(bundle.get("reference_events", [])),
        "reference_events": bundle.get("reference_events", []),
        "roles": bundle.get("roles", {}),
    }
