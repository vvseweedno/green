from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass(frozen=True)
class Evidence:
    family: Literal["sentinel2", "gfc", "modis", "cci"]
    strength: Literal["strong", "partial", "weak"]
    direction: Literal["loss", "gain", "unknown"]
    date_min: date | None = None
    date_max: date | None = None
    supports_fire: bool = False
    note: str | None = None


def _interval(evidence: list[Evidence]):
    lows = [e.date_min for e in evidence if e.date_min]
    highs = [e.date_max for e in evidence if e.date_max]
    if not lows or not highs:
        return None, None, False
    low = max(lows)
    high = min(highs)
    if low <= high:
        return low, high, False
    return min(lows), max(highs), True


def _date_precision(low: date | None, high: date | None, conflict: bool) -> str:
    if low is None or high is None:
        return "unknown"
    if conflict:
        return "conflict_envelope"
    days = (high - low).days
    if days == 0:
        return "day"
    if days <= 7:
        return "week"
    if days <= 31:
        return "month"
    if days <= 366:
        return "year_interval"
    return "multi_year_interval"


def fuse_event(evidence: list[Evidence]) -> dict:
    if not evidence:
        return {
            "confidence": "uncertain",
            "cause": None,
            "cause_status": "cause_not_established",
            "date_min": None,
            "date_max": None,
            "date_precision": "unknown",
            "date_conflict": False,
            "evidence_families": [],
        }
    strong_families = {e.family for e in evidence if e.strength == "strong"}
    any_families = {e.family for e in evidence if e.strength in {"strong", "partial"}}
    if len(strong_families) >= 2:
        confidence = "confirmed"
    elif len(strong_families) >= 1 and len(any_families) >= 2:
        confidence = "probable"
    else:
        confidence = "uncertain"
    low, high, conflict = _interval(evidence)
    sentinel_fire_compatible = any(
        e.family == "sentinel2" and e.direction == "loss" and e.strength in {"strong", "partial"}
        for e in evidence
    )
    modis_fire = any(
        e.family == "modis" and e.supports_fire and e.strength in {"strong", "partial"}
        for e in evidence
    )
    fire = sentinel_fire_compatible and modis_fire and not conflict
    return {
        "confidence": confidence,
        "cause": "fire" if fire else None,
        "cause_status": "established" if fire else "cause_not_established",
        "date_min": low.isoformat() if low else None,
        "date_max": high.isoformat() if high else None,
        "date_precision": _date_precision(low, high, conflict),
        "date_conflict": conflict,
        "evidence_families": sorted(any_families),
    }
