# Requirements trace

| Requirement | Implementation | Evidence |
|---|---|---|
| Exact carbon math/sign | `carbon/stock.py` | `tests/unit/test_carbon.py` |
| Exact geodesic area / partial pixel | `geometry/area.py` | `test_geometry.py` |
| Same AOI / multi-parent disjoint partition | `data/local.py`, `analysis/pipeline.py` | runtime partition + judge transfer case |
| Official baseline formula | `carbon/baseline.py` | `test_baseline.py` |
| Q formula + edge cases | `carbon/credits.py` | golden + edge tests |
| Golden Q=395 | `tests/golden/test_credits_golden.py` | automated |
| Partial coverage blocks Q | `quality/coverage.py`, `credits.py` | tests |
| SCL policy inside AOI | `quality/scl.py`, `data/stac.py` | tests + acquisition path |
| Prepared S2 no second /10000 | `data/sentinel2.py` | strict dataset scale/offset validator |
| Prepared S2 arbitrary CRS | `geometry/reproject.py`, `data/sentinel2.py`, `change/objects.py` | production + research pipeline |
| Scene IDs/radiometry/version metadata | `data/scene_index.py`, `data/metadata.py` | run provenance / event QA |
| Dynamic Earth Search | `data/stac.py`, `fetch_demo_data.py` | forced online mode |
| Online → cache → offline replay | `data/cache.py`, `fetch_demo_data.py` | checksum/replay unit test |
| file_catalog integrity | `data/catalog.py`, `verify_dataset.py` | strict validator |
| All required metadata/tables consumed | `data/metadata.py` | `test_metadata.py` + provenance |
| events.csv leakage guard | `data/metadata.py` role declaration | never imported by detector/change modules |
| GFC decoding | `data/gfc.py` | tests |
| MODIS QA | `data/modis.py` | tests |
| MODIS uncertainty + First/Last day | `data/external_evidence.py` | `test_external_evidence.py` |
| Robust annual composites | `change/composites.py` | research/production pipeline |
| Multi-index robust change maps | `change/transitions.py` | research/production pipeline |
| Connected objects | `change/objects.py` | production + research |
| Explicit confidence rule | `change/fusion.py` | fusion tests |
| Fire only with MODIS+Sentinel | `change/fusion.py` | tests |
| Date interval + date precision + conflict | `change/fusion.py` | fusion tests |
| Event E contribution | `carbon/contribution.py` | production event payload |
| Official CCI change temporal diagnostic | `data/cci_change.py`, `uncertainty/temporal.py` | research CSV + run assumptions |
| Spatial+temporal correlated MC | `uncertainty/monte_carlo.py` | deterministic seed test |
| Before/after Sentinel evidence | `reporting/imagery.py`, API preview, frontend, HTML report | guarded preview + embedded report |
| API | `api/app.py` | analysis/layers/events/provenance/report/areas/preview routes |
| Browser UI | `frontend/` | offline map, AOI selector/upload, events, evidence, waterfall |
| Self-contained HTML + JSON report | `reporting/report.py` | embedded evidence + audit payload |
| Dataset integrity | `scripts/verify_dataset.py` | schema/hash/raster/coverage checks |
| Changed/control/3-method research | `research/run_experiments.py` | data-gated CSVs |
| External evidence agreement metrics | `research/run_experiments.py` | object/area support rates; explicitly not ground truth |
| Demo suite | `scripts/run_demo_suite.py` | changed/control/transfer reports + manifest |
| Transfer proof | `tests/integration/test_official_dataset.py`, `make demo`, `make judge` | CHECK_TRANSFER_01 |
| Deterministic replay | `scripts/judge_preflight.py` | double-run canonical hash comparison |
| Judge preflight | `scripts/judge_preflight.py` | verify → tests → changed/control/transfer → reports → scorecard |
| Python + frontend CI | `.github/workflows/ci.yml` | compile/tests + npm build |
