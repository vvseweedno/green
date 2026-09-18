from __future__ import annotations

import html
import json
from pathlib import Path


def write_report(result: dict, output_dir: str | Path) -> tuple[Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    run_id = str(result.get("run_id", "analysis"))
    json_path = out / f"{run_id}.json"
    html_path = out / f"{run_id}.html"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    stock = result["stock"]
    credits = result["credits"]
    unc = result.get("uncertainty") or {}
    prov = result.get("provenance", {})
    body = f"""<!doctype html><html><head><meta charset='utf-8'><title>MRV {html.escape(run_id)}</title>
<style>body{{font-family:system-ui;max-width:1000px;margin:40px auto;padding:0 20px;color:#17211b}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccd6cf;padding:8px;text-align:left}}pre{{overflow:auto;background:#eef2ef;padding:12px}}.warn{{background:#fff4d6;padding:12px;border-left:4px solid #c48b00}}</style></head><body>
<h1>Satellite Carbon MRV Verification Report</h1>
<p><b>Run:</b> {html.escape(run_id)}</p>
<p><b>Period:</b> {result['request']['year_start']}–{result['request']['year_end']}</p>
<h2>Carbon stock difference</h2>
<table><tr><th>Metric</th><th>Value</th></tr>
<tr><td>Requested area</td><td>{result['coverage']['requested_area_ha']:.3f} ha</td></tr>
<tr><td>Computed area</td><td>{result['coverage']['computed_area_ha']:.3f} ha</td></tr>
<tr><td>E</td><td>{stock['E_tco2e']:.3f} tCO2e</td></tr>
<tr><td>e</td><td>{stock['e_tco2e_ha_year']:.6f} tCO2e/ha/year</td></tr>
<tr><td>Uncertainty L–U</td><td>{unc.get('L')} – {unc.get('U')}</td></tr>
<tr><td>Potential Q</td><td>{credits.get('Q')} ({html.escape(credits.get('status',''))})</td></tr></table>
<h2>Credits waterfall inputs</h2><pre>{html.escape(json.dumps(credits, indent=2, ensure_ascii=False))}</pre>
<h2>Provenance</h2><pre>{html.escape(json.dumps(prov, indent=2, ensure_ascii=False))}</pre>
<h2>Limitations</h2><div class='warn'><ul>{''.join(f'<li>{html.escape(x)}</li>' for x in result.get('limitations', []))}</ul></div>
<p><b>Statement:</b> Potential units are outputs of the hackathon scenario, not certified carbon credits.</p>
</body></html>"""
    html_path.write_text(body, encoding="utf-8")
    return html_path, json_path
