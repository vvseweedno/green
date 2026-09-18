from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from carbon_mrv.data.provenance import sha256_file


class ArrayCache:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _base(self, key: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in key)
        return self.root / safe

    def put(self, key: str, arrays: dict[str, np.ndarray], metadata: dict[str, Any]) -> dict[str, Any]:
        base = self._base(key)
        npz = base.with_suffix(".npz")
        meta = base.with_suffix(".json")
        np.savez_compressed(npz, **arrays)
        enriched = {**metadata, "artifact": npz.name, "sha256": sha256_file(npz)}
        meta.write_text(json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8")
        return enriched

    def get(self, key: str):
        base = self._base(key)
        npz = base.with_suffix(".npz")
        meta = base.with_suffix(".json")
        if not npz.exists() or not meta.exists():
            return None
        metadata = json.loads(meta.read_text(encoding="utf-8"))
        if sha256_file(npz) != metadata.get("sha256"):
            raise ValueError(f"Cache checksum mismatch for {key}")
        with np.load(npz) as z:
            arrays = {name: z[name] for name in z.files}
        return arrays, metadata
