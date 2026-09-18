from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from affine import Affine
from rasterio.features import shapes
from scipy import ndimage
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from carbon_mrv.geometry.area import geodesic_area_ha

@dataclass(frozen=True)
class ChangeObject:
    object_id:str; geometry:BaseGeometry; area_ha:float; pixel_count:int; mean_score:float

def connected_objects(mask:np.ndarray,score:np.ndarray,transform:Affine,*,min_area_ha:float=0.25):
    binary=np.asarray(mask,dtype=bool); labels,n=ndimage.label(binary,structure=np.ones((3,3),dtype=np.uint8)); out=[]
    for label_id in range(1,n+1):
        obj=labels==label_id
        if not np.any(obj): continue
        geoms=[shape(g) for g,value in shapes(obj.astype(np.uint8),mask=obj,transform=transform) if value==1]
        if not geoms: continue
        geom=geoms[0]
        for g in geoms[1:]: geom=geom.union(g)
        area=geodesic_area_ha(geom)
        if area<min_area_ha: continue
        out.append(ChangeObject(f"chg-{label_id:04d}",geom,area,int(obj.sum()),float(np.nanmean(np.asarray(score,dtype=float)[obj]))))
    return out
