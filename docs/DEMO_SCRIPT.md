# 5–7 minute jury demo

**0:00–0:40 — problem.** This is an MRV verifier, not a black-box biomass model. CCI is the carbon stock source; Sentinel/GFC/MODIS localize, date and explain evidence.

**0:40–1:30 — request.** Open the UI, select/draw a valid AOI, choose 2020→2022 and run. Point out requested/computed area and coverage reason.

**1:30–2:20 — carbon.** Show start/end tC, ΔC, E and e. Open formula audit and emphasize exact geodesic partial-pixel weighting and sign semantics.

**2:20–3:20 — change events.** Toggle before/after imagery and change objects. Open one event: interval, evidence families, confidence, cause status and contribution to E. If fire is shown, demonstrate MODIS+Sentinel evidence. If evidence conflicts, show the conflict rather than hiding it.

**3:20–4:20 — uncertainty.** Switch independent/moderate/strong assumptions. Show L/U, H/R and how Q changes. Say explicitly: model-based interval, not field-calibrated confidence interval.

**4:20–5:10 — credits waterfall.** Ebase → Eproj → R → uncertainty deduction → 15% buffer → floor → Q. State that Q is potential units under the case, not certified credits.

**5:10–6:00 — provenance.** Open scene IDs, versions, scale/offset, checksums, config hash and cache replay.

**6:00–7:00 — proof.** Show `make test`, research changed/control tables, then run the transfer sub-polygon without code changes.
