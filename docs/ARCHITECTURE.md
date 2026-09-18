# Architecture

The system is a verification pipeline rather than a model-training pipeline. The invariant is: **published CCI AGB controls carbon stock; other sensors explain where/when/why the stock signal may have changed**.

## Domain boundaries

1. **Geometry** validates WGS84 polygon requests and calculates exact geodesic overlap.
2. **Data adapters** read official local products or a dynamic Sentinel-2 STAC source.
3. **Quality** applies explicit SCL and coverage rules.
4. **Change** builds optical indices, robust annual composites and connected change objects.
5. **Evidence fusion** combines independent data families without collapsing disagreement into a fake single truth.
6. **Carbon** computes stock, official baseline, event contribution and Q.
7. **Uncertainty** models stated spatial/temporal dependence scenarios.
8. **Analysis** orchestrates pure modules; business math is not duplicated in UI.
9. **Reporting/provenance** stores machine-readable evidence and a verifier-readable report.

## Transferability

No calculation is keyed to the four known AOIs. Parent AOIs are loaded from `areas.geojson`; CCI paths are discovered from the dataset tree; query geometry is intersected with parents at runtime. Therefore a valid sub-polygon can run without code edits, provided its required data/baseline coverage exists.

## Failure semantics

The system distinguishes invalid request, unavailable data, partial coverage, baseline missing, uncertainty unavailable and cause not established. Those states are never coerced into a numeric zero.
