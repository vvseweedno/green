from __future__ import annotations

import argparse
import json
from pathlib import Path

from carbon_mrv.analysis.pipeline import analyze_local
from carbon_mrv.domain.models import AnalysisRequest
from carbon_mrv.reporting.report import write_report


def main():
    parser = argparse.ArgumentParser(prog="carbon-mrv")
    sub = parser.add_subparsers(dest="cmd", required=True)
    analyze = sub.add_parser("analyze")
    analyze.add_argument("--request", required=True, help="JSON file containing AnalysisRequest")
    analyze.add_argument("--dataset", default="data/raw")
    analyze.add_argument("--runs", default="runs")
    args = parser.parse_args()
    if args.cmd == "analyze":
        req = AnalysisRequest.model_validate_json(Path(args.request).read_text(encoding="utf-8"))
        result = analyze_local(req, args.dataset)
        result["run_id"] = result.get("run_id") or Path(args.request).stem
        html_path, json_path = write_report(result, args.runs)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        print(f"report={html_path} json={json_path}")


if __name__ == "__main__":
    main()
