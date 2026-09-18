from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from carbon_mrv.data.provenance import sha256_file


@dataclass(frozen=True)
class CatalogCheck:
    path: str
    exists: bool
    size_ok: bool | None
    hash_ok: bool | None
    message: str


def _first_column(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    lower = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate in lower:
            return lower[candidate]
    return None


def verify_file_catalog(dataset_root: str | Path, csv_path: str | Path) -> list[CatalogCheck]:
    root = Path(dataset_root)
    df = pd.read_csv(csv_path)
    pcol = _first_column(df, ("path", "file", "relative_path", "filepath", "filename"))
    hcol = _first_column(df, ("sha256", "checksum", "hash"))
    scol = _first_column(df, ("size_bytes", "bytes", "size"))
    if pcol is None:
        raise ValueError("file_catalog.csv has no recognizable path column")
    results: list[CatalogCheck] = []
    for _, row in df.iterrows():
        rel = str(row[pcol])
        path = root / rel
        exists = path.exists()
        size_ok = None
        hash_ok = None
        msg = "ok"
        if not exists:
            msg = "missing"
        else:
            if scol and pd.notna(row[scol]):
                size_ok = path.stat().st_size == int(row[scol])
                if not size_ok:
                    msg = "size_mismatch"
            if hcol and pd.notna(row[hcol]) and str(row[hcol]).strip():
                expected = str(row[hcol]).strip().lower().replace("sha256:", "")
                hash_ok = sha256_file(path).lower() == expected
                if not hash_ok:
                    msg = "hash_mismatch"
        results.append(CatalogCheck(rel, exists, size_ok, hash_ok, msg))
    return results
