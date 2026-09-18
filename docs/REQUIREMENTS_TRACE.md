# Requirements trace

| Requirement | Implementation | Evidence |
|---|---|---|
| Exact carbon math/sign | `carbon/stock.py` | `tests/unit/test_carbon.py` |
| Exact geodesic area | `geometry/area.py` | `test_geometry.py` |
| Official baseline formula | `carbon/baseline.py` | `test_baseline.py` |
| Q formula + edge cases | `carbon/credits.py` | golden + edge tests |
| Golden Q=395 | `tests/golden/test_credits_golden.py` | automated |
| Partial coverage blocks Q | `quality/coverage.py`, `credits.py` | tests |
| SCL quality policy | `quality/scl.py` | tests |
| No second /10000 for prepared S2 | `data/sentinel2.py` | code/doc invariant |
| Dynamic STAC | `data/stac.py`, `fetch_demo_data.py` | requires network run |
| Cache + checksum | `data/cache.py` | implementation |
| GFC decoding | `data/gfc.py` | tests |
| MODIS QA | `data/modis.py` | tests |
| Robust change maps | `change/*` | research pipeline |
| Connected objects | `change/objects.py` | implementation |
| Fire only with MODIS+Sentinel | `change/fusion.py` | tests |
| Event E contribution | `carbon/contribution.py` | implementation |
| Temporal dependence diagnostic | `uncertainty/temporal.py` | tests |
| Spatial+temporal correlated MC | `uncertainty/monte_carlo.py` | deterministic test |
| API | `api/app.py` | route contract |
| Browser UI | `frontend/` | React + MapLibre |
| HTML+JSON report | `reporting/report.py` | implementation |
| Dataset integrity | `scripts/verify_dataset.py` | data-gated |
| Research changed/control/sensitivity | `research/run_experiments.py` | data-gated; no fabricated outputs |
| Judge preflight | `scripts/judge_preflight.py` | fails if official data absent |
