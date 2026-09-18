# 100-point scorecard readiness

This scorecard separates **implemented code** from **real-data proof**. No point is claimed as empirically proven until the official dataset run is available.

| Criterion | Pts | Implementation | Test/demo evidence | Current proof state |
|---|---:|---|---|---|
| Practical verifier flow | 10 | FastAPI + React + report | API/UI + report path | implemented; real-data demo pending dataset |
| Change analysis | 10 | indices/composites/objects/fusion/contribution | fusion tests + research runner | implemented; real scene output pending |
| Research | 10 | `research/run_experiments.py` | changed/control/sensitivity CSVs | protocol implemented; numbers pending |
| Presentation | 5 | demo script, report, UI | repository docs | implemented |
| Extra verifier features | 5 | uncertainty scenario switch + provenance | UI/API/config | implemented core; price scenario not yet added |
| Data preparation | 10 | local adapters + Earth Search + cache | fetch script | online adapter implemented; network proof pending |
| Forest change technical | 12 | robust S2 change + evidence fusion | research runner | implementation ready; dataset proof pending |
| Carbon correctness | 10 | stock/area/sign | unit tests | **proven by tests** |
| Potential units | 8 | official formula | golden Q=395 + edge tests | **proven by tests** |
| Uncertainty | 10 | temporal diagnostic + correlated MC | deterministic tests | **proven algorithmically; sensitivity pending data** |
| Architecture/quality | 5 | separated typed modules | CI/tests | implemented |
| Documentation | 5 | README + method/provenance/trace | docs | implemented |

## Blocking evidence before final submission

1. Mount official dataset and make `verify-data` green.
2. Run online Earth Search once and save cache/provenance.
3. Run changed (`RU_MORDOVIA_03`), control (`RU_TVER_01`) and `CHECK_TRANSFER_01` end-to-end.
4. Execute research and commit real CSV/figures only after inspection.
5. Validate event contribution and report outputs against those runs.
6. Run `make judge` twice from cache and confirm byte-equivalent machine-readable summaries where deterministic.
