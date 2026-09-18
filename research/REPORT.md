# Research report

This file is intentionally a **protocol before the official dataset run**, not a fabricated results section.

`research/run_experiments.py` writes quantitative artifacts only from the mounted official dataset:

- `site_summary.csv` — changed/control/additional AOI carbon and production-scenario outputs;
- `uncertainty_sensitivity.csv` — independent/moderate/strong dependence assumptions versus L/U, H/R and Q;
- `temporal_rho_diagnostic.csv` — implied 2019→2020 temporal correlation from annual CCI SD and official CCI Change SD;
- `baseline_sensitivity.csv` — official baseline versus research-only no-change counterfactual;
- `change_method_comparison.csv` — dNBR, multi-index, and multi-index+temporal-observation methods;
- `change_threshold_sensitivity.csv` — robust-z threshold stability.

The changed site is `RU_MORDOVIA_03`; the control is `RU_TVER_01`. Prepared Sentinel imagery is processed in its actual raster CRS and change objects are reprojected to WGS84 for geodesic area and external-evidence intersection.

## Numerical external-evidence measures

For every change method, the runner reports:

- GFC-supported fraction of detected objects;
- GFC-supported fraction of detected object area;
- MODIS-supported fraction of detected objects;
- MODIS-supported fraction of detected object area;
- detected area/object count;
- mean valid-observation counts before/after.

These are **satellite-to-satellite evidence support rates**, not ground-truth accuracy. GFC/MODIS are not used to train the detector in the same comparison.

## Required interpretation after execution

1. Report all methods, including false-looking/control-site behavior; do not publish only the best-looking detector.
2. Do not select the narrowest uncertainty scenario merely because it increases Q.
3. Keep the official baseline as the only production Q; no-change baseline remains research-only sensitivity.
4. Treat CCI Change implied rho as a diagnostic of temporal dependence, not independent calibration.
5. Describe GFC/MODIS disagreement as evidence disagreement, not independent validation.
6. Preserve config hash, file checksums, random seed, scene IDs and processing metadata with every reported result.
7. If a required data product is absent or fails integrity checks, leave the corresponding result unavailable instead of filling a value by hand.
