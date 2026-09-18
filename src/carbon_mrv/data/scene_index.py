from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class SceneRow:
    aoi_id: str
    observed_at: datetime
    reflectance_path: Path
    scl_path: Path
    scene_id: str | None = None
    metadata: dict[str, Any] | None = None


def _col(df: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    lower = {c.lower(): c for c in df.columns}
    return next((lower[n] for n in names if n in lower), None)


def _metadata_index(raw: Any) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}

    def add(token: Any, payload: dict[str, Any]):
        if token is None:
            return
        value = str(token)
        index[value] = payload
        index[Path(value).name] = payload

    def walk(node: Any, inherited_key: str | None = None):
        if isinstance(node, dict):
            identity_keys = (
                "scene_id", "item_id", "id", "name", "filename", "file",
                "path", "reflectance_path", "image_path", "raster_path",
            )
            for key in identity_keys:
                if key in node:
                    add(node.get(key), node)
            if inherited_key is not None:
                add(inherited_key, node)
            for key, value in node.items():
                if isinstance(value, (dict, list)):
                    walk(value, str(key))
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(raw)
    return index


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
    id_col = _col(df, ("scene_id", "item_id", "id", "scene"))
    if not all((aoi_col, date_col, refl_col, scl_col)):
        raise ValueError(
            "scenes.csv must expose AOI/date/reflectance/SCL path columns; "
            f"found columns={list(df.columns)}"
        )

    def resolve(value: str) -> Path:
        p = Path(str(value))
        if p.is_absolute() and p.exists():
            return p
        for base in (table.parent, root):
            q = base / p
            if q.exists():
                return q
        return root / p

    metadata_path = next(iter(root.rglob("scene_metadata.json")), None)
    metadata_index: dict[str, dict[str, Any]] = {}
    if metadata_path is not None:
        metadata_index = _metadata_index(json.loads(metadata_path.read_text(encoding="utf-8")))

    rows = []
    for _, row in df.iterrows():
        refl = resolve(row[refl_col])
        scene_id = str(row[id_col]) if id_col and pd.notna(row[id_col]) else None
        candidates = [scene_id, str(row[refl_col]), Path(str(row[refl_col])).name, refl.name]
        metadata = next((metadata_index[c] for c in candidates if c and c in metadata_index), None)
        rows.append(
            SceneRow(
                aoi_id=str(row[aoi_col]),
                observed_at=pd.to_datetime(row[date_col], utc=True).to_pydatetime(),
                reflectance_path=refl,
                scl_path=resolve(row[scl_col]),
                scene_id=scene_id,
                metadata=metadata,
            )
        )
    return rows
