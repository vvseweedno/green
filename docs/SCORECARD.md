# 100-point scorecard readiness

This scorecard separates **implemented code** from **real-data proof**. No empirical result is claimed until the official competition dataset is mounted and the data-gated suite is executed.

| Criterion | Pts | Implementation | Test/demo evidence | Current proof state |
|---|---:|---|---|---|
| Practical verifier flow | 10 | FastAPI + offline-capable React/MapLibre UI + self-contained report | AOI selector/upload, carbon cards, events, before/after previews, report | implemented; real-data demo pending dataset |
| Change analysis | 10 | indices/composites/objects/fusion/contribution | fusion/date tests + research runner | implemented; real-scene proof pending |
| Research | 10 | `research/run_experiments.py` | changed/control, 3 detectors, threshold/baseline/uncertainty sensitivity, GFC/MODIS support rates | protocol implemented; numbers pending |
| Presentation | 5 | `make demo`, HTML/JSON, trajectory, image evidence, demo script, jury Q&A | changed/control/transfer artifact suite | implemented; artifacts pending dataset |
| Extra verifier features | 5 | uncertainty scenarios + provenance + post-Q price scenarios | UI/API/config/report | implemented |
| Data preparation | 10 | local adapters + Earth Search + request-hash cache | explicit online/auto/offline modes + checksum tamper test | implemented; live-network proof pending |
| Forest change technical | 12 | robust S2 change, projected-grid geometry, GFC/MODIS/CCI fusion | research runner + event outputs | implemented; dataset proof pending |
| Carbon correctness | 10 | stock/exact area/sign/same AOI | unit tests | **proven by tests** |
| Potential units | 8 | official formula + fail-closed availability | golden Q=395 + edge tests | **proven by tests** |
| Uncertainty | 10 | correlated Monte Carlo + official CCI Change temporal-rho diagnostic | deterministic tests + data-gated diagnostic CSV | algorithm proven; real-data sensitivity pending |
| Architecture/quality | 5 | separated typed modules, no UI math, CORS, safe preview paths | Python + frontend CI | implemented |
| Documentation | 5 | README + methodology/provenance/trace/demo/jury docs | repository docs | implemented |

## Evidence gates before final submission

1. Mount the official dataset and make `make verify-data` green.
2. Run one forced `--mode online` Earth Search acquisition and preserve cache/provenance; replay with `--mode offline`.
3. Run `make demo`: changed `RU_MORDOVIA_03`, control `RU_TVER_01`, and `CHECK_TRANSFER_01`.
4. Run `make research` and inspect/commit numerical CSVs only after they are actually produced.
5. Review event carbon contributions, before/after evidence, temporal-rho diagnostic and report provenance.
6. Run `make judge`; it verifies data, tests, changed/control/transfer runs, deterministic replay, reports and prints this scorecard.
7. Only after all gates pass freeze a submission commit/tag. Do not replace missing proof with hand-written numbers.
