import math
from affine import Affine
from shapely.geometry import box
from carbon_mrv.geometry.area import geodesic_area_ha,iter_pixel_overlaps

def test_geodesic_area_not_degree_area():
    area=geodesic_area_ha(box(30.0,50.0,30.01,50.01)); assert 70<area<90

def test_partial_pixel_overlap_exact_area():
    transform=Affine(0.01,0,30,0,-0.01,50.01); half=box(30,50,30.005,50.01)
    overlaps=list(iter_pixel_overlaps(half,transform,1,1)); assert len(overlaps)==1
    assert math.isclose(overlaps[0].area_ha,geodesic_area_ha(half),rel_tol=1e-10)
