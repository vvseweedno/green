#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from carbon_mrv.data.provenance import sha256_file
from carbon_mrv.reporting.golden import default_golden_cases, run_golden_case


def main() -> int:
    ap=argparse.ArgumentParser(
        description="Freeze real-data golden summaries only after strict dataset verification"
    )
    ap.add_argument("--dataset",default="data/raw")
    ap.add_argument("--output",default="tests/golden/fixtures")
    ap.add_argument("--simulations",type=int,default=500)
    ap.add_argument("--seed",type=int,default=20260918)
    ap.add_argument("--force",action="store_true")
    args=ap.parse_args()

    dataset=Path(args.dataset)
    if not dataset.exists():
        raise SystemExit("Official dataset is missing; golden fixtures cannot be fabricated")
    subprocess.run(
        [sys.executable,"scripts/verify_dataset.py",str(dataset)],
        check=True,
    )

    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True)
    cases=default_golden_cases(dataset)
    written=[]
    for case in cases:
        path=out/f"{case.name}.json"
        if path.exists() and not args.force:
            raise SystemExit(f"{path} already exists; use --force only after intentional model/method review")
        summary=run_golden_case(
            case,dataset,simulations=args.simulations,seed=args.seed
        )
        path.write_text(
            json.dumps(summary,indent=2,ensure_ascii=False,sort_keys=True,default=str),
            encoding="utf-8",
        )
        written.append(str(path))

    catalog=next(iter(dataset.rglob("file_catalog.csv")),None)
    manifest={
        "dataset_root":str(dataset.resolve()),
        "file_catalog_sha256":sha256_file(catalog) if catalog else None,
        "simulations":args.simulations,
        "seed":args.seed,
        "cases":[case.name for case in cases],
        "files":written,
        "policy":"Generated from verified official data; never hand-edit numeric fields.",
    }
    (out/"manifest.json").write_text(
        json.dumps(manifest,indent=2,ensure_ascii=False,sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(manifest,indent=2,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
