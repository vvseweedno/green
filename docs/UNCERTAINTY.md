# Uncertainty model

The repository does **not** assume that CCI per-pixel/per-year errors are independent.

## Temporal diagnostic

For 2019→2020, when CCI change SD is present, an implied temporal correlation can be diagnosed:

```text
rho_t = (sigma_2019² + sigma_2020² - sigma_delta²) / (2 sigma_2019 sigma_2020)
```

Values outside [-1,1] are counted before clipping. Median/IQR are diagnostics, not independent calibration.

## Correlated Monte Carlo

For each simulation:

1. draw a spatial Gaussian random field for t0;
2. draw an independent spatial field;
3. combine them to enforce configured temporal rho at t1;
4. multiply each field by per-pixel AGB SD;
5. recompute exact-area weighted stock difference;
6. collect E.

Spatial correlation length and temporal rho are explicit. The default config exposes three scenarios: independent, moderate and strong. A fixed seed supports exact replay.

The reported L/U are model-based quantiles under those assumptions. They must not be described as field-calibrated confidence intervals.

## Production scenario selection

`configs/uncertainty.yaml` marks the default as **provisional until the official dataset sensitivity experiment is executed**. The production choice must not be made by selecting whichever scenario maximizes Q.
