from __future__ import annotations

import html
import json
from pathlib import Path


def _sparkline(points: list[dict], width: int = 720, height: int = 180) -> str:
    vals = [float(p["mean_carbon_t_ha"]) for p in points]
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    span = max(hi - lo, 1e-9)
    xs = [20 + i * (width - 40) / max(1, len(vals) - 1) for i in range(len(vals))]
    ys = [height - 20 - (v - lo) / span * (height - 40) for v in vals]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys, strict=True))
    labels = "".join(
        f"<text x='{x:.1f}' y='{height-3}' font-size='10' text-anchor='middle'>{p['year']}</text>"
        for x, p in zip(xs, points, strict=True)
    )
    dots = "".join(
        f"<circle cx='{x:.1f}' cy='{y:.1f}' r='3'/><text x='{x:.1f}' y='{y-8:.1f}' font-size='10' text-anchor='middle'>{v:.2f}</text>"
        for x, y, v in zip(xs, ys, vals, strict=True)
    )
    return f"<svg viewBox='0 0 {width} {height}' role='img'><polyline points='{path}' fill='none' stroke='#1f6f43' stroke-width='3'/>{dots}{labels}</svg>"


def _event_rows(events: list[dict]) -> str:
    rows = []
    for e in events:
        cc = e.get("carbon_contribution") or {}
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(e.get('event_id','')))}</td>"
            f"<td>{html.escape(str(e.get('direction','')))}</td>"
            f"<td>{float(e.get('area_ha',0)):.3f}</td>"
            f"<td>{html.escape(str(e.get('confidence','')))}</td>"
            f"<td>{html.escape(str(e.get('cause') or 'not established'))}</td>"
            f"<td>{html.escape(str(e.get('date_min')))} — {html.escape(str(e.get('date_max')))}</td>"
            f"<td>{cc.get('E_event_tco2e','')}</td>"
            "</tr>"
        )
    return "".join(rows) or "<tr><td colspan='7'>No change objects established from available observations.</td></tr>"


def write_report(result: dict, output_dir: str | Path) -> tuple[Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    run_id = str(result.get("run_id", "analysis"))
    json_path = out / f"{run_id}.json"
    html_path = out / f"{run_id}.html"
    json_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    stock = result["stock"]
    credits = result["credits"]
    unc = result.get("uncertainty") or {}
    prov = result.get("provenance", {})
    events = result.get("events", [])
    geometry = result.get("request", {}).get("geometry", {})
    body = f"""<!doctype html><html><head><meta charset='utf-8'><title>MRV {html.escape(run_id)}</title>
<style>body{{font-family:system-ui;max-width:1080px;margin:40px auto;padding:0 20px;color:#17211b}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccd6cf;padding:8px;text-align:left;vertical-align:top}}pre{{overflow:auto;background:#eef2ef;padding:12px}}.warn{{background:#fff4d6;padding:12px;border-left:4px solid #c48b00}}svg{{width:100%;background:#f7faf7;border:1px solid #dce5dd;border-radius:8px}}code{{background:#eef2ef;padding:2px 4px}}</style></head><body>
<h1>Satellite Carbon MRV Verification Report</h1>
<p><b>Run:</b> {html.escape(run_id)}<br><b>Created UTC:</b> {html.escape(str(result.get('created_at_utc','')))}<br><b>Period:</b> {result['request']['year_start']}–{result['request']['year_end']}</p>
<h2>AOI & coverage</h2><table><tr><th>Requested</th><th>Computed</th><th>Coverage</th><th>Missing</th></tr><tr><td>{result['coverage']['requested_area_ha']:.3f} ha</td><td>{result['coverage']['computed_area_ha']:.3f} ha</td><td>{result['coverage']['coverage_ratio']:.4%}</td><td>{result['coverage']['missing_area_ha']:.3f} ha</td></tr></table>
<h2>Carbon stock difference</h2><table><tr><th>Metric</th><th>Value</th></tr><tr><td>Start stock</td><td>{stock['start']['total_carbon_t']:.3f} tC</td></tr><tr><td>End stock</td><td>{stock['end']['total_carbon_t']:.3f} tC</td></tr><tr><td>ΔC</td><td>{stock['delta_c_t']:.3f} tC</td></tr><tr><td>E</td><td>{stock['E_tco2e']:.3f} tCO2e</td></tr><tr><td>e</td><td>{stock['e_tco2e_ha_year']:.6f} tCO2e/ha/year</td></tr><tr><td>Model interval L–U</td><td>{unc.get('L')} – {unc.get('U')}</td></tr><tr><td>Potential Q</td><td>{credits.get('Q')} ({html.escape(credits.get('status',''))})</td></tr></table>
<h2>2019–2024 mean carbon trajectory</h2>{_sparkline(stock.get('yearly', []))}
<h2>Change events</h2><table><thead><tr><th>ID</th><th>Type</th><th>Area ha</th><th>Confidence</th><th>Cause</th><th>Date interval</th><th>E_event</th></tr></thead><tbody>{_event_rows(events)}</tbody></table>
<h2>Credits waterfall & price sensitivity</h2><pre>{html.escape(json.dumps(credits, indent=2, ensure_ascii=False))}</pre>
<h2>Uncertainty assumptions</h2><pre>{html.escape(json.dumps(unc, indent=2, ensure_ascii=False, default=str))}</pre>
<h2>Provenance</h2><pre>{html.escape(json.dumps(prov, indent=2, ensure_ascii=False))}</pre>
<h2>AOI GeoJSON</h2><pre>{html.escape(json.dumps(geometry, ensure_ascii=False))}</pre>
<h2>Event evidence & geometries</h2><pre>{html.escape(json.dumps(events, indent=2, ensure_ascii=False, default=str))}</pre>
<h2>Limitations</h2><div class='warn'><ul>{''.join(f'<li>{html.escape(x)}</li>' for x in result.get('limitations', []))}</ul></div>
<p><b>Statement:</b> Potential units are outputs of the hackathon scenario, not certified carbon credits. Price outputs are illustrative scenarios, not market forecasts.</p>
</body></html>"""
    html_path.write_text(body, encoding="utf-8")
    return html_path, json_path
