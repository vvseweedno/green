from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from shapely.geometry import shape

from carbon_mrv.carbon.baseline import BaselineTrajectory


@dataclass(frozen=True)
class ParentAOI:
    aoi_id: str
    geometry: object


class LocalDataset:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if not self.root.exists():
            raise FileNotFoundError(self.root)

    def find(self, name: str) -> Path | None:
        exact = list(self.root.rglob(name))
        return exact[0] if exact else None

    def require(self, name: str) -> Path:
        path = self.find(name)
        if path is None:
            raise FileNotFoundError(f"Required dataset file not found: {name}")
        return path

    def parent_aois(self) -> list[ParentAOI]:
        path = self.require("areas.geojson")
        data = json.loads(path.read_text(encoding="utf-8"))
        out = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            aoi = props.get("aoi_id") or props.get("id") or props.get("name")
            if not aoi:
                raise ValueError("areas.geojson feature missing aoi_id/id/name")
            out.append(ParentAOI(str(aoi), shape(feature["geometry"])))
        return out

    def intersecting_parents(self, geometry) -> list[tuple[ParentAOI, object]]:
        # Deterministic disjoint partition: overlapping parent footprints can never double-count area.
        parts = []
        covered = None
        for parent in sorted(self.parent_aois(), key=lambda p: p.aoi_id):
            inter = parent.geometry.intersection(geometry)
            if covered is not None and not covered.is_empty:
                inter = inter.difference(covered)
            if not inter.is_empty and inter.area > 0:
                parts.append((parent, inter))
                covered = inter if covered is None else covered.union(inter)
        return parts

    def cci_path(self, aoi_id: str, year: int) -> Path | None:
        target = f"CCI_Biomass_{year}.tif"
        candidates = [p for p in self.root.rglob(target) if aoi_id.lower() in str(p).lower()]
        if not candidates:
            candidates = list(self.root.rglob(target))
            if len(candidates) == 1:
                return candidates[0]
            return None
        return candidates[0]

    def baseline_trajectories(self) -> dict[str, BaselineTrajectory]:
        path = self.require("baseline.csv")
        df = pd.read_csv(path)
        lower = {c.lower(): c for c in df.columns}
        id_col = next((lower[k] for k in ("aoi_id", "parent_aoi_id", "id") if k in lower), None)
        if id_col is None:
            raise ValueError("baseline.csv missing AOI id column")
        c15 = next((lower[k] for k in ("cbar_2015", "cbar_2015_tc_ha", "cbar2015") if k in lower), None)
        c19 = next((lower[k] for k in ("cbar_2019", "cbar_2019_tc_ha", "cbar2019") if k in lower), None)
        result: dict[str, BaselineTrajectory] = {}
        if c15 and c19:
            for _, row in df.iterrows():
                result[str(row[id_col])] = BaselineTrajectory(str(row[id_col]), float(row[c15]), float(row[c19]))
            return result
        year_col = lower.get("year")
        cbar_col = next((lower[k] for k in ("cbar", "mean_carbon_tc_ha", "carbon_tc_ha") if k in lower), None)
        if year_col and cbar_col:
            for aoi, group in df.groupby(id_col):
                values = {int(r[year_col]): float(r[cbar_col]) for _, r in group.iterrows()}
                if 2015 in values and 2019 in values:
                    result[str(aoi)] = BaselineTrajectory(str(aoi), values[2015], values[2019])
            return result
        raise ValueError("baseline.csv schema unsupported")


    def baseline_consistency_report(
        self,
        *,
        rel_tol: float = 1e-6,
        abs_tol: float = 1e-6,
    ) -> dict:
        """Check official baseline rows against the mandated trajectory formula when possible."""
        path = self.require("baseline.csv")
        df = pd.read_csv(path)
        lower = {c.lower(): c for c in df.columns}
        id_col = next(
            (lower[k] for k in ("aoi_id", "parent_aoi_id", "id") if k in lower),
            None,
        )
        if id_col is None:
            raise ValueError("baseline.csv missing AOI id column")
        trajectories = self.baseline_trajectories()
        checks: list[dict] = []

        year_col = lower.get("year")
        cbar_col = next(
            (
                lower[k]
                for k in ("cbar", "cbase", "mean_carbon_tc_ha", "carbon_tc_ha")
                if k in lower
            ),
            None,
        )
        if year_col and cbar_col:
            for _, row in df.iterrows():
                aoi = str(row[id_col])
                if aoi not in trajectories or pd.isna(row[year_col]) or pd.isna(row[cbar_col]):
                    continue
                year = int(row[year_col])
                observed = float(row[cbar_col])
                expected = trajectories[aoi].cbar(year)
                checks.append({
                    "aoi_id": aoi,
                    "year": year,
                    "official": observed,
                    "formula": expected,
                    "ok": math.isclose(
                        observed, expected, rel_tol=rel_tol, abs_tol=abs_tol
                    ),
                })
        else:
            wide_columns: list[tuple[str, int]] = []
            for column in df.columns:
                match = re.search(r"(?:cbar|cbase)[_\-]?(20\d{2}|2015)", column.lower())
                if match:
                    wide_columns.append((column, int(match.group(1))))
            for _, row in df.iterrows():
                aoi = str(row[id_col])
                if aoi not in trajectories:
                    continue
                for column, year in wide_columns:
                    if pd.isna(row[column]):
                        continue
                    observed = float(row[column])
                    expected = trajectories[aoi].cbar(year)
                    checks.append({
                        "aoi_id": aoi,
                        "year": year,
                        "column": column,
                        "official": observed,
                        "formula": expected,
                        "ok": math.isclose(
                            observed, expected, rel_tol=rel_tol, abs_tol=abs_tol
                        ),
                    })

        mismatches = [row for row in checks if not row["ok"]]
        return {
            "path": str(path.relative_to(self.root)),
            "checked_values": len(checks),
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
            "status": (
                "consistent"
                if checks and not mismatches
                else "mismatch"
                if mismatches
                else "anchors_only_or_unrecognized_schema"
            ),
        }
