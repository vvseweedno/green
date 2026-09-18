# Jury Q&A

**Why not train a neural network for biomass?** There is no independent ground biomass label in the case sufficient to justify a custom biomass model. The verifier preserves ESA CCI AGB as the published stock source and uses higher-resolution sensors for change evidence.

**Is E an atmospheric emission?** No. It is the CO2-equivalent expression of stock difference in the accounted above-ground live woody biomass pool.

**Why not sum all pixel SDs as independent?** Spatial and temporal error dependence is material. We expose correlated Monte Carlo scenarios and a temporal-rho diagnostic instead of pretending independence.

**Is your interval a 95% confidence interval?** No. It is a model-based quantile interval under explicit correlation assumptions unless independent field calibration is later added.

**Does GFC prove fire?** No. GFC is evidence of stand-replacement loss. Fire cause requires compatible MODIS burn evidence and Sentinel optical disturbance.

**Does MODIS give exact burned area?** No. Its 500 m grid is used as cause/timing evidence, not exact geometry.

**Why can Q become unavailable rather than zero?** Zero is a valid calculated outcome. Missing baseline/full coverage is an inability to calculate, which must remain distinguishable.

**Can a new polygon run?** Yes. AOIs are runtime geometry intersections with parent coverage. The code is not keyed to the four demos; transferability is validated with `sample_requests.geojson` once the dataset is mounted.

**How do you prevent cherry-picking uncertainty?** Scenarios are visible, research compares them, and the default is marked provisional until sensitivity is executed. The narrowest interval is never automatically selected.
