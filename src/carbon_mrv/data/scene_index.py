from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class SceneRow:
    aoi_id: str
    observed_at: datetime
    reflectance_path: Path
    scl_path: Path


def _col(df: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    lower = {c.lower(): c for c in df.columns}
    return next((lower[n] for n in names if n in lower), None)


def load_scene_rows(dataset_root: str | Path) -> list[SceneRow]:
    root = Path(dataset_root)
    matches = list(root.rglob("scenes.csv"))
    if not matches:
        raise FileNotFoundError("scenes.csv")
    table = matches[0]
    df = pd.read_csv(table)
    aoi_col = _col(df, ("aoi_id", "area_id", "site_id"))
    date_col = _col(df, ("datetime", "date", "acquired_at", "sensing_time"))
    refl_col = _col(df, ("reflectance_path", "image_path", "raster_path", "reflectance"))
    scl_col = _col(df, ("scl_path", "scene_classification_path", "scl"))
    if not all((aoi_col, date_col, refl_col, scl_col)):
        raise ValueError(f"Unsupported scenes.csv schema: {list(df.columns)}")

    def resolve(value: str) -> Path:
        p = Path(str(value))
        if p.is_absolute() and p.exists():
            return p
        for base in (table.parent, root):
            q = base / p
            if q.exists():
                return q
        return root / p

    return [
        SceneRow(
            str(row[aoi_col]),
            pd.to_datetime(row[date_col], utc=True).to_pydatetime(),
            resolve(row[refl_col]),
            resolve(row[scl_col]),
        )
        for _, row in df.iterrows()
    ]
