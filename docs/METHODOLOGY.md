# Methodology

## Carbon stock

For each CCI pixel, AGB in Mg dry matter/ha is multiplied by `CF=0.47` to obtain tC/ha. The value is multiplied by the **exact AOI/pixel intersection area in ha**. The same AOI boundary is used at both dates.

`E = -(C_t1 - C_t0) * 44/12`. Positive E is stock loss; negative E is stock accumulation. The accounted pool is live above-ground woody biomass. Roots, deadwood, litter, soil and harvested wood products are outside the core calculation.

## Sentinel-2

Prepared competition rasters are already scaled. Online Earth Search COGs apply each STAC asset's declared `raster:bands` scale/offset. SCL quality is evaluated **inside the request AOI**.

Annual change uses robust composites of NDVI/NBR/NDMI. Thresholds are configuration and research parameters, not hidden constants. The baseline implementation uses median/MAD z-scores, multi-index agreement and minimum connected area.

## GFC

`lossyear` is decoded as `2000 + code` for positive codes. GFC is evidence of stand-replacement forest loss; it is not a biomass estimate and does not establish fire/logging cause.

## MODIS MCD64A1

A positive Burn_Date is used only where QA bit 0 is land and bit 1 indicates sufficient valid data. Burn_Date_Uncertainty plus First_Day/Last_Day constrain timing. The 500 m pixel is not used as exact burn geometry.

## Evidence fusion

`confirmed` requires at least two strong independent data families. `probable` requires one strong family plus another partial/strong family. Otherwise the event remains `uncertain`.

`fire` requires compatible MODIS burn evidence and Sentinel disturbance evidence. Conflicting time intervals are flagged and never silently averaged.

## Event carbon contribution

Change geometry is intersected with CCI pixel footprints. Each overlap receives that CCI pixel's Δcarbon. The resulting `E_event` is a contribution to the observed stock-change signal, not automatically a causal attribution to fire/logging.
