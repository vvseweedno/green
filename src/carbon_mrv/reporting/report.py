from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from carbon_mrv.reporting.imagery import render_prepared_rgb_png


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
    return (
        f"<svg viewBox='0 0 {width} {height}' role='img'>"
        f"<polyline points='{path}' fill='none' stroke='#1f6f43' stroke-width='3'/>"
        f"{dots}{labels}</svg>"
    )


def _event_rows(events: list[dict]) -> str:
    rows = []
    for event in events:
        cc = event.get("carbon_contribution") or {}
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(event.get('event_id','')))}</td>"
            f"<td>{html.escape(str(event.get('direction','')))}</td>"
            f"<td>{float(event.get('area_ha',0)):.3f}</td>"
            f"<td>{html.escape(str(event.get('confidence','')))}</td>"
            f"<td>{html.escape(str(event.get('cause') or 'not established'))}</td>"
            f"<td>{html.escape(str(event.get('date_min')))} — "
            f"{html.escape(str(event.get('date_max')))} "
            f"({html.escape(str(event.get('date_precision','unknown')))})</td>"
            f"<td>{cc.get('E_event_tco2e','')}</td>"
            "</tr>"
        )
    return (
        "".join(rows)
        or "<tr><td colspan='7'>No change objects established from available observations.</td></tr>"
    )


def _safe_data_uri(
    dataset_root: Path | None,
    relative_path: str | None,
    cache: dict[str, str | None],
) -> str | None:
    if dataset_root is None or not relative_path:
        return None
    if relative_path in cache:
        return cache[relative_path]
    root = dataset_root.resolve()
    target = (root / relative_path).resolve()
    if not target.is_relative_to(root) or not target.exists():
        cache[relative_path] = None
        return None
    try:
        payload = render_prepared_rgb_png(target, max_size=720)
        uri = "data:image/png;base64," + base64.b64encode(payload).decode("ascii")
    except Exception:  # report generation should preserve partial evidence
        uri = None
    cache[relative_path] = uri
    return uri


def _best_quality_scene(quality: list[dict], stage: str) -> dict | None:
    candidates = [
        q for q in quality
        if q.get("stage") == stage and q.get("reflectance_path")
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda q: float(
            q.get("strict_valid_fraction")
            if q.get("strict_valid_fraction") is not None
            else q.get("valid_fraction") or 0.0
        ),
    )


def _evidence_gallery(events: list[dict], dataset_root: Path | None, limit: int = 12) -> str:
    if not events:
        return "<p>No event image evidence available.</p>"
    cache: dict[str, str | None] = {}
    blocks = []
    for event in events[:limit]:
        quality = event.get("data_quality") or []
        before = _best_quality_scene(quality, "before")
        after = _best_quality_scene(quality, "after")
        b_uri = _safe_data_uri(dataset_root, (before or {}).get("reflectance_path"), cache)
        a_uri = _safe_data_uri(dataset_root, (after or {}).get("reflectance_path"), cache)
        images = []
        for label, q, uri in (("Before", before, b_uri), ("After", after, a_uri)):
            if uri:
                images.append(
                    "<figure>"
                    f"<figcaption><b>{label}</b> {html.escape(str((q or {}).get('date','')))}</figcaption>"
                    f"<img src='{uri}' alt='{label} Sentinel-2 evidence'/>"
                    "</figure>"
                )
            else:
                images.append(
                    f"<div class='img-missing'><b>{label}</b><br>No embedded referenced scene.</div>"
                )
        evidence = html.escape(
            json.dumps(event.get("evidence", []), ensure_ascii=False, default=str)
        )
        blocks.append(
            "<details>"
            f"<summary>{html.escape(str(event.get('event_id','')))} · "
            f"{html.escape(str(event.get('direction','')))} · "
            f"{html.escape(str(event.get('confidence','')))}</summary>"
            f"<div class='scene-grid'>{''.join(images)}</div>"
            f"<pre>{evidence}</pre>"
            "</details>"
        )
    return "".join(blocks)



def _outer_rings(geometry: dict) -> list[list[list[float]]]:
    if not isinstance(geometry, dict):
        return []
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    if kind == "Polygon":
        return [coordinates[0]] if coordinates else []
    if kind == "MultiPolygon":
        return [polygon[0] for polygon in coordinates if polygon]
    return []


def _map_svg(aoi: dict, events: list[dict], width: int = 720, height: int = 460) -> str:
    """Self-contained WGS84 evidence map for the saved report.

    This intentionally has no external basemap dependency. It visualizes the exact request
    geometry and vector change objects; satellite evidence remains in the adjacent image gallery.
    """
    aoi_rings = _outer_rings(aoi)
    if not aoi_rings:
        return "<p>Map unavailable: AOI geometry is missing or unsupported.</p>"
    points = [p for ring in aoi_rings for p in ring if len(p) >= 2]
    if not points:
        return "<p>Map unavailable: AOI has no coordinates.</p>"
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    dx = max(maxx - minx, 1e-9)
    dy = max(maxy - miny, 1e-9)
    pad = 28.0
    scale = min((width - 2 * pad) / dx, (height - 2 * pad) / dy)
    used_w, used_h = dx * scale, dy * scale
    x0 = (width - used_w) / 2.0
    y0 = (height - used_h) / 2.0

    def project(point):
        x, y = float(point[0]), float(point[1])
        return x0 + (x - minx) * scale, height - (y0 + (y - miny) * scale)

    def path_for(ring):
        coords = [project(p) for p in ring if len(p) >= 2]
        if not coords:
            return ""
        return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in coords) + " Z"

    aoi_paths = "".join(
        f"<path d='{path_for(ring)}' fill='#dfeee4' stroke='#176b3a' stroke-width='2.2'/>"
        for ring in aoi_rings
    )
    event_paths = []
    labels = []
    for event in events:
        direction = str(event.get("direction", "unknown"))
        fill = "#edb5a8" if direction == "disturbance" else "#afd2e6" if direction == "recovery" else "#d0d0d0"
        for ring in _outer_rings(event.get("geometry") or {}):
            d = path_for(ring)
            if not d:
                continue
            event_paths.append(
                f"<path d='{d}' fill='{fill}' fill-opacity='0.55' stroke='#333' stroke-width='1'/>"
            )
            projected = [project(p) for p in ring if len(p) >= 2]
            if projected:
                cx = sum(p[0] for p in projected) / len(projected)
                cy = sum(p[1] for p in projected) / len(projected)
                labels.append(
                    f"<text x='{cx:.1f}' y='{cy:.1f}' font-size='9' text-anchor='middle'>"
                    f"{html.escape(str(event.get('event_id','')))}</text>"
                )
    extent = (
        f"{minx:.5f}, {miny:.5f} → {maxx:.5f}, {maxy:.5f}"
    )
    return (
        f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='AOI and change objects map'>"
        f"<rect width='{width}' height='{height}' fill='#f7faf7'/>"
        f"{aoi_paths}{''.join(event_paths)}{''.join(labels)}"
        f"<text x='12' y='18' font-size='10'>WGS84 extent: {extent}</text>"
        f"<text x='{width-16}' y='22' font-size='14' text-anchor='end'>N ↑</text>"
        "<g transform='translate(12,34)'><rect width='12' height='12' fill='#dfeee4' stroke='#176b3a'/>"
        "<text x='18' y='10' font-size='10'>AOI</text>"
        "<rect x='58' width='12' height='12' fill='#edb5a8' stroke='#333'/>"
        "<text x='76' y='10' font-size='10'>disturbance</text>"
        "<rect x='150' width='12' height='12' fill='#afd2e6' stroke='#333'/>"
        "<text x='168' y='10' font-size='10'>recovery</text></g>"
        "</svg>"
        "<p class='caption'>Self-contained geometry map; no external basemap. "
        "MODIS footprints are not treated as exact burn geometry.</p>"
    )

def write_report(
    result: dict,
    output_dir: str | Path,
    dataset_root: str | Path | None = None,
) -> tuple[Path, Path]:
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
    gallery = _evidence_gallery(
        events, Path(dataset_root) if dataset_root is not None else None
    )
    body = f"""<!doctype html><html><head><meta charset='utf-8'><title>MRV {html.escape(run_id)}</title>
<style>
body{{font-family:system-ui;max-width:1080px;margin:40px auto;padding:0 20px;color:#17211b}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccd6cf;padding:8px;text-align:left;vertical-align:top}}
pre{{overflow:auto;background:#eef2ef;padding:12px;max-height:520px}}.warn{{background:#fff4d6;padding:12px;border-left:4px solid #c48b00}}
svg{{width:100%;background:#f7faf7;border:1px solid #dce5dd;border-radius:8px}}code{{background:#eef2ef;padding:2px 4px}}
details{{border:1px solid #dce5dd;border-radius:8px;padding:10px;margin:10px 0}}summary{{font-weight:700;cursor:pointer}}
.scene-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:10px 0}}figure{{margin:0}}figcaption{{padding:6px;background:#f3f6f3}}
img{{max-width:100%;display:block}}.caption{{font-size:11px;color:#667}}.img-missing{{min-height:160px;border:1px dashed #ccd6cf;display:grid;place-items:center;text-align:center;color:#667}}
@media(max-width:720px){{.scene-grid{{grid-template-columns:1fr}}}}
</style></head><body>
<h1>Satellite Carbon MRV Verification Report</h1>
<p><b>Run:</b> {html.escape(run_id)}<br><b>Created UTC:</b> {html.escape(str(result.get('created_at_utc','')))}<br><b>Period:</b> {result['request']['year_start']}–{result['request']['year_end']}</p>
<h2>AOI & coverage</h2><table><tr><th>Requested</th><th>Computed</th><th>Coverage</th><th>Missing</th></tr><tr><td>{result['coverage']['requested_area_ha']:.3f} ha</td><td>{result['coverage']['computed_area_ha']:.3f} ha</td><td>{result['coverage']['coverage_ratio']:.4%}</td><td>{result['coverage']['missing_area_ha']:.3f} ha</td></tr></table>
<h2>Method & exact formulas</h2>
<pre>c_i,t = AGB_i,t × 0.47
C_t = Σ(exact_intersection_area_i_ha × c_i,t)
cbar_t = C_t / A
ΔC = C_t1 - C_t0
E = -ΔC × 44/12
e = E / (A × Δt)

baseline: g=(cbar_2019-cbar_2015)/4; cbase,y=max(0,cbar_2019+g(y-2019))
Ebase=-A(cbase,t1-cbase,t0)×44/12

R=Ebase-Eproj-LK; LK=0
H=max(Eproj-L, U-Eproj)
if R≤0: Q=0
elif H/R≥1: Q=0
else UNC=min(1,max(0,H/R-0.10)); Radj=R(1-UNC); B=0.15×Radj; Q=floor(0.85×Radj)

Sign: E&gt;0 = loss of accounted live above-ground woody biomass carbon; E&lt;0 = accumulation.
E is not presented as a direct atmospheric-emission measurement.</pre>
<h2>Carbon stock difference</h2><table><tr><th>Metric</th><th>Value</th></tr><tr><td>Start stock</td><td>{stock['start']['total_carbon_t']:.3f} tC</td></tr><tr><td>End stock</td><td>{stock['end']['total_carbon_t']:.3f} tC</td></tr><tr><td>ΔC</td><td>{stock['delta_c_t']:.3f} tC</td></tr><tr><td>E</td><td>{stock['E_tco2e']:.3f} tCO2e</td></tr><tr><td>e</td><td>{stock['e_tco2e_ha_year']:.6f} tCO2e/ha/year</td></tr><tr><td>Model interval L–U</td><td>{unc.get('L')} – {unc.get('U')}</td></tr><tr><td>Potential Q</td><td>{credits.get('Q')} ({html.escape(credits.get('status',''))})</td></tr></table>
<h2>2019–2024 mean carbon trajectory</h2>{_sparkline(stock.get('yearly', []))}
<h2>AOI & change-object map</h2>{_map_svg(geometry, events)}
<h2>Change events</h2><table><thead><tr><th>ID</th><th>Type</th><th>Area ha</th><th>Confidence</th><th>Cause</th><th>Date interval / precision</th><th>E_event</th></tr></thead><tbody>{_event_rows(events)}</tbody></table>
<h2>Before / after evidence</h2>{gallery}
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
