# Dataset placement

The official competition dataset is intentionally **not** committed to Git.
Mount or copy it under `data/raw/` (or pass a different root to CLI/scripts).

The code discovers `areas.geojson`, `baseline.csv`, `file_catalog.csv`, CCI rasters and other
metadata recursively, so it does not depend on a developer's absolute path.

Run `make verify-data` before any analysis. A missing dataset is a hard failure; the repository
never fabricates research numbers or golden outputs.
