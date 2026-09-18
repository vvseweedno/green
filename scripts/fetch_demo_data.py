#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from shapely.geometry import shape

from carbon_mrv.data.cache import ArrayCache
from carbon_mrv.data.provenance import canonical_json_hash
from carbon_mrv.data.stac import rank_candidates, read_scene, search_items


def _replay(cache: ArrayCache, request_hash: str) -> list[dict]:
    outputs = []
    for arrays, metadata in cache.replay_by_request_hash(request_hash):
        outputs.append({
            "mode": "offline_replay",
            "item_id": metadata.get("item_id"),
            "datetime": metadata.get("datetime"),
            "sha256": metadata.get("sha256"),
            "artifact": metadata.get("artifact"),
            "request_hash": metadata.get("request_hash"),
            "array_shapes": {name: list(arr.shape) for name, arr in arrays.items()},
            "aoi_scl_quality": metadata.get("aoi_scl_quality"),
        })
    return outputs


def main():
    ap = argparse.ArgumentParser(
        description="Earth Search Sentinel-2 AOI acquisition with checksummed offline replay"
    )
    ap.add_argument("--geometry", required=True, help="GeoJSON Feature/geometry file")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--count", type=int, default=2)
    ap.add_argument("--cache", default="data/cache/sentinel2")
    ap.add_argument(
        "--mode",
        choices=("auto", "online", "offline"),
        default="auto",
        help="auto replays matching cache first; online forces STAC; offline never uses network",
    )
    args = ap.parse_args()
    raw = json.loads(Path(args.geometry).read_text(encoding="utf-8"))
    geometry_json = raw.get("geometry", raw)
    geom = shape(geometry_json)
    request_hash = canonical_json_hash({
        "geometry": geometry_json,
        "start": args.start,
        "end": args.end,
    })
    cache = ArrayCache(args.cache)

    if args.mode in {"auto", "offline"}:
        replay = _replay(cache, request_hash)
        if replay:
            print(json.dumps(replay[: args.count], indent=2, ensure_ascii=False))
            return
        if args.mode == "offline":
            raise SystemExit(
                f"No valid cached Sentinel-2 artifacts for request_hash={request_hash}"
            )

    items = search_items(geometry_json, args.start, args.end)
    ranked = rank_candidates(items, geom)
    if not ranked:
        raise SystemExit("No Sentinel-2 L2A candidates found")
    manifests = []
    for candidate in ranked[: args.count]:
        arrays, metadata = read_scene(candidate.item, geom)
        metadata["aoi_scl_quality"] = {
            "valid_fraction": candidate.valid_fraction,
            "strict_valid_fraction": candidate.strict_valid_fraction,
            "low_confidence_fraction": candidate.low_confidence_fraction,
        }
        metadata["request_hash"] = request_hash
        saved = cache.put(candidate.item.id, arrays, metadata)
        manifests.append({"mode": "online_cached", **saved})
    print(json.dumps(manifests, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
