from datetime import date, timedelta
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from carbon_mrv.data.external_evidence import modis_fire_evidence


def _write(path: Path, value: int, dtype: str):
    with rasterio.open(
        path,"w",driver="GTiff",height=1,width=1,count=1,dtype=dtype,
        crs="EPSG:4326",transform=from_origin(0,1,0.1,0.1)
    ) as dst:
        dst.write(np.array([[value]],dtype=dtype),1)


def test_modis_interval_uses_uncertainty_and_first_last_day(tmp_path: Path):
    prefix="RU_MORDOVIA_03_2021_"
    _write(tmp_path/f"{prefix}Burn_Date.tif",250,"int16")
    _write(tmp_path/f"{prefix}Burn_Date_Uncertainty.tif",5,"int16")
    _write(tmp_path/f"{prefix}QA.tif",3,"uint8")
    _write(tmp_path/f"{prefix}First_Day.tif",248,"int16")
    _write(tmp_path/f"{prefix}Last_Day.tif",252,"int16")
    out=modis_fire_evidence(tmp_path,"RU_MORDOVIA_03",box(0,0.9,0.1,1.0),2021)
    assert out is not None
    assert out["date_min"]==date(2021,1,1)+timedelta(days=247)
    assert out["date_max"]==date(2021,1,1)+timedelta(days=251)
    assert out["first_day_constraint_used"] is True
    assert out["last_day_constraint_used"] is True
