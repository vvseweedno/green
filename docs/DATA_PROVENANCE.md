# Data provenance

Every reproducible run should preserve:

- source product and version;
- scene/item IDs and acquisition times;
- STAC collection and asset URLs for dynamic acquisitions;
- processing baseline when published;
- band scale/offset metadata;
- AOI-valid SCL fractions;
- SHA-256 of clipped/cache artifacts and official dataset files used;
- processing-config hash;
- random seed and uncertainty scenario.

`scripts/verify_dataset.py` uses `file_catalog.csv` and validates discoverable raster integrity. `src/carbon_mrv/data/cache.py` refuses cache replay if its SHA-256 does not match metadata.

## External references implemented against

- Element 84 Earth Search v1: `https://earth-search.aws.element84.com/v1`
- Sentinel-2 L2A collection: `sentinel-2-l2a` with COG assets including `nir08`, `swir16`, `swir22`, `scl`
- ESA CCI Biomass v7.0 documentation/data portal
- Hansen Global Forest Change 2025 v1.13
- NASA LP DAAC MCD64A1 Collection 6.1 User Guide

These sources guide the adapters; the competition-provided files and metadata remain authoritative for the submitted offline demo.
