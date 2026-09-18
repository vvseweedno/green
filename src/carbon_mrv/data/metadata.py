from __future__ import annotations

import json
import math
import re
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



def _normalize_parameter_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _numeric_parameter(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    percent = "%" in text
    ratio = re.fullmatch(r"\s*([-+]?\d+(?:\.\d+)?)\s*/\s*([-+]?\d+(?:\.\d+)?)\s*", text)
    if ratio:
        denominator = float(ratio.group(2))
        if denominator == 0:
            return None
        return float(ratio.group(1)) / denominator
    match = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    return number / 100.0 if percent else number


def methodology_parameter_consistency(parameters: dict[str, Any]) -> dict[str, Any]:
    """Check only recognized case constants; preserve unknown parameters without guessing."""
    expected = {
        "carbon_fraction": (0.47, {
            "cf", "carbon_fraction", "biomass_carbon_fraction",
        }),
        "co2_per_c": (44.0 / 12.0, {
            "co2_per_c", "co2_c_ratio", "co2_to_c", "co2_carbon_ratio",
        }),
        "leakage": (0.0, {
            "lk", "leakage", "leakage_tco2e",
        }),
        "buffer_fraction": (0.15, {
            "buffer", "buffer_fraction", "buffer_rate", "reserve_fraction",
        }),
        "uncertainty_free_band": (0.10, {
            "uncertainty_free_band", "uncertainty_threshold",
            "unc_free_threshold", "free_uncertainty_threshold",
        }),
    }
    normalized = {
        _normalize_parameter_name(str(key)): (str(key), value)
        for key, value in parameters.items()
    }
    checks = []
    matched_keys: set[str] = set()
    for semantic_name, (expected_value, aliases) in expected.items():
        for alias in aliases:
            if alias not in normalized:
                continue
            original_key, raw = normalized[alias]
            numeric = _numeric_parameter(raw)
            ok = numeric is not None and math.isclose(
                numeric, expected_value, rel_tol=1e-9, abs_tol=1e-12
            )
            checks.append({
                "semantic_name": semantic_name,
                "parameter_key": original_key,
                "raw_value": raw,
                "numeric_value": numeric,
                "expected": expected_value,
                "ok": ok,
            })
            matched_keys.add(original_key)
            break
    mismatches = [check for check in checks if not check["ok"]]
    return {
        "recognized_checks": checks,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "uninterpreted_keys": [
            key for key in parameters if key not in matched_keys
        ],
        "policy": (
            "Only recognized official case constants are compared. Unknown keys are "
            "preserved for provenance and never silently mapped to formulas."
        ),
    }
