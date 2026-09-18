from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from carbon_mrv.analysis.pipeline import analyze_local
from carbon_mrv.data.local import LocalDataset
from carbon_mrv.domain.models import AnalysisRequest


@dataclass(frozen=True)
class GoldenCase:
    name: str
    request: AnalysisRequest


def _sample_years(properties: dict) -> tuple[int, int]:
    y0 = properties.get("year_start") or properties.get("start_year") or properties.get("t0")
    y1 = properties.get("year_end") or properties.get("end_year") or properties.get("t1")
    if y0 is None or y1 is None:
        raise ValueError("CHECK_TRANSFER_01 is missing start/end year properties")
    return int(y0), int(y1)


def default_golden_cases(dataset_root: str | Path) -> list[GoldenCase]:
    ds = LocalDataset(dataset_root)
    parents = {p.aoi_id: p for p in ds.parent_aois()}
    cases: list[GoldenCase] = []
    for aoi_id, name in (
        ("RU_MORDOVIA_03", "changed_RU_MORDOVIA_03_2020_2022"),
        ("RU_TVER_01", "control_RU_TVER_01_2020_2022"),
    ):
        if aoi_id not in parents:
            raise ValueError(f"Missing golden AOI: {aoi_id}")
        cases.append(
            GoldenCase(
                name,
                AnalysisRequest(
                    geometry=parents[aoi_id].geometry.__geo_interface__,
                    year_start=2020,
                    year_end=2022,
                    data_mode="offline",
                    parent_aoi_id=aoi_id,
                    uncertainty_scenario="moderate",
                ),
            )
        )

    payload = json.loads(ds.require("sample_requests.geojson").read_text(encoding="utf-8"))
    transfer = None
    for feature in payload.get("features", []):
        props = feature.get("properties") or {}
        fid = props.get("request_id") or props.get("id") or props.get("name") or feature.get("id")
        if str(fid) == "CHECK_TRANSFER_01":
            transfer = feature
            break
    if transfer is None:
        raise ValueError("CHECK_TRANSFER_01 not found")
    y0, y1 = _sample_years(transfer.get("properties") or {})
    cases.append(
        GoldenCase(
            "transfer_CHECK_TRANSFER_01",
            AnalysisRequest(
                geometry=transfer["geometry"],
                year_start=y0,
                year_end=y1,
                data_mode="offline",
                uncertainty_scenario="moderate",
            ),
        )
    )
    return cases


def stable_summary(result: dict) -> dict:
    """Strip timestamps/presentation while keeping every scoring-sensitive numeric output."""
    return {
        "request": {
            "year_start": result["request"]["year_start"],
            "year_end": result["request"]["year_end"],
            "parent_aoi_id": result["request"].get("parent_aoi_id"),
            "uncertainty_scenario": result["request"]["uncertainty_scenario"],
        },
        "coverage": result["coverage"],
        "stock": {
            "yearly": result["stock"]["yearly"],
            "start": result["stock"]["start"],
            "end": result["stock"]["end"],
            "delta_c_t": result["stock"]["delta_c_t"],
            "E_tco2e": result["stock"]["E_tco2e"],
            "e_tco2e_ha_year": result["stock"]["e_tco2e_ha_year"],
        },
        "uncertainty": result.get("uncertainty"),
        "baseline": result.get("baseline"),
        "credits": result.get("credits"),
        "events": [
            {
                "event_id": event.get("event_id"),
                "area_ha": event.get("area_ha"),
                "direction": event.get("direction"),
                "confidence": event.get("confidence"),
                "cause": event.get("cause"),
                "cause_status": event.get("cause_status"),
                "date_min": event.get("date_min"),
                "date_max": event.get("date_max"),
                "date_precision": event.get("date_precision"),
                "date_conflict": event.get("date_conflict"),
                "evidence_families": event.get("evidence_families"),
                "carbon_contribution": event.get("carbon_contribution"),
            }
            for event in result.get("events", [])
        ],
        "processing_config_hash": result.get("provenance", {}).get("processing_config_hash"),
    }


def run_golden_case(
    case: GoldenCase,
    dataset_root: str | Path,
    *,
    simulations: int = 500,
    seed: int = 20260918,
) -> dict:
    return stable_summary(
        analyze_local(
            case.request,
            dataset_root,
            simulations=simulations,
            seed=seed,
        )
    )
