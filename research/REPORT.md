# Research report

This file is intentionally a **protocol before the dataset run**, not a fabricated results section.

`research/run_experiments.py` writes quantitative artifacts only from the mounted official dataset:

- `site_summary.csv` — changed/control/additional AOI carbon and production scenario outputs;
- `uncertainty_sensitivity.csv` — dependence assumptions versus L/U, H/R and Q;
- `baseline_sensitivity.csv` — official baseline versus research-only no-change counterfactual;
- `change_method_comparison.csv` — dNBR vs multi-index vs multi-index+temporal consistency;
- `change_threshold_sensitivity.csv` — threshold stability.

The changed site is `RU_MORDOVIA_03`, the control is `RU_TVER_01`. GFC/MODIS are external evidence/proxies, not ground truth and are not used to train/tune the detector when their agreement is reported.

## Required interpretation after execution

1. Report all methods, including negative/control-site behavior.
2. Do not select the narrowest uncertainty scenario merely because it increases Q.
3. Keep the official baseline as the only production Q; alternatives remain sensitivity analysis.
4. Describe satellite-to-satellite disagreement as evidence disagreement, not independent validation.
5. Preserve every config/hash in generated run artifacts.
