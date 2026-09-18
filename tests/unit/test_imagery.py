from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from carbon_mrv.reporting.imagery import render_prepared_rgb_png


def test_render_prepared_rgb_png(tmp_path: Path):
    path=tmp_path/"sentinel.tif"
    data=np.zeros((6,10,12),dtype=np.float32)
    data[0]=0.05
    data[1]=np.linspace(0.05,0.25,120,dtype=np.float32).reshape(10,12)
    data[2]=np.linspace(0.1,0.6,120,dtype=np.float32).reshape(10,12)
    data[3]=0.4;data[4]=0.2;data[5]=0.1
    with rasterio.open(
        path,"w",driver="GTiff",height=10,width=12,count=6,dtype="float32",
        crs="EPSG:4326",transform=from_origin(30,60,0.001,0.001)
    ) as dst:
        dst.write(data)
    png=render_prepared_rgb_png(path,max_size=100)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(png)>50
