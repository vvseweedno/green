#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from carbon_mrv.analysis.pipeline import analyze_local
from carbon_mrv.domain.models import AnalysisRequest
from carbon_mrv.reporting.report import write_report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True)
    ap.add_argument("--dataset", default="data/raw")
    ap.add_argument("--runs", default="runs")
    args = ap.parse_args()
    req = AnalysisRequest.model_validate_json(Path(args.request).read_text(encoding="utf-8"))
    result = analyze_local(req, args.dataset)
    result["run_id"] = Path(args.request).stem
    result["created_at_utc"] = datetime.now(timezone.utc).isoformat()
    html, js = write_report(result, args.runs, args.dataset)
    print(json.dumps({"report": str(html), "json": str(js), "credits": result["credits"]}, indent=2))


if __name__ == "__main__":
    main()
