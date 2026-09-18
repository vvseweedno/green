from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from carbon_mrv.data.cci_change import temporal_rho_from_official_change


def _annual(path: Path, agb: float, sd: float):
    data=np.array([[[agb]],[[sd]]],dtype=np.float32)
    with rasterio.open(
        path,"w",driver="GTiff",height=1,width=1,count=2,dtype="float32",
        crs="EPSG:4326",transform=from_origin(30,60,0.01,0.01)
    ) as dst:
        dst.write(data)


def _change(path: Path, delta: float, sd_delta: float, flag: float):
    data=np.array([[[delta]],[[sd_delta]],[[flag]]],dtype=np.float32)
    with rasterio.open(
        path,"w",driver="GTiff",height=1,width=1,count=3,dtype="float32",
        crs="EPSG:4326",transform=from_origin(30,60,0.01,0.01)
    ) as dst:
        dst.write(data)


def test_official_change_sd_yields_temporal_rho_diagnostic(tmp_path: Path):
    site=tmp_path/"RU_TVER_01";site.mkdir()
    _annual(site/"CCI_Biomass_2019.tif",100,10)
    _annual(site/"CCI_Biomass_2020.tif",101,10)
    _change(site/"CCI_Change_2019_2020.tif",1,10,1)
    out=temporal_rho_from_official_change(
        tmp_path,"RU_TVER_01",box(30,59.99,30.01,60)
    )
    assert out is not None
    assert out["median"]==pytest.approx(0.5)
    assert out["n"]==1
    assert out["quality_flag_histogram"]=={"1":1}
