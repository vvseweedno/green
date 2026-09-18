from __future__ import annotations

import json
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
        parts = []
        for parent in self.parent_aois():
            inter = parent.geometry.intersection(geometry)
            if not inter.is_empty and inter.area > 0:
                parts.append((parent, inter))
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
