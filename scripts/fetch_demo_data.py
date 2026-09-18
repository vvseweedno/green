#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from shapely.geometry import shape

from carbon_mrv.data.cache import ArrayCache
from carbon_mrv.data.stac import rank_candidates, read_scene, search_items
from carbon_mrv.data.provenance import canonical_json_hash


def main():
    ap = argparse.ArgumentParser(description="Fetch/cache clipped Sentinel-2 L2A scenes from Earth Search")
    ap.add_argument("--geometry", required=True, help="GeoJSON Feature/geometry file")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--count", type=int, default=2)
    ap.add_argument("--cache", default="data/cache/sentinel2")
    args = ap.parse_args()
    raw = json.loads(Path(args.geometry).read_text(encoding="utf-8"))
    geometry_json = raw.get("geometry", raw)
    geom = shape(geometry_json)
    items = search_items(geometry_json, args.start, args.end)
    ranked = rank_candidates(items, geom)
    if not ranked:
        raise SystemExit("No Sentinel-2 L2A candidates found")
    cache = ArrayCache(args.cache)
    manifests = []
    for candidate in ranked[: args.count]:
        arrays, metadata = read_scene(candidate.item, geom)
        metadata["aoi_scl_quality"] = {
            "valid_fraction": candidate.valid_fraction,
            "strict_valid_fraction": candidate.strict_valid_fraction,
            "low_confidence_fraction": candidate.low_confidence_fraction,
        }
        metadata["request_hash"] = canonical_json_hash({"geometry": geometry_json, "start": args.start, "end": args.end})
        manifests.append(cache.put(candidate.item.id, arrays, metadata))
    print(json.dumps(manifests, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
