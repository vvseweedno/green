import json
from pathlib import Path

from shapely.geometry import box, mapping

from carbon_mrv.data.local import LocalDataset
from carbon_mrv.geometry.area import geodesic_area_ha


def test_intersecting_parents_are_disjoint_even_if_parent_footprints_overlap(tmp_path: Path):
    a=box(30.0,60.0,30.02,60.02)
    b=box(30.01,60.0,30.03,60.02)
    query=box(30.0,60.0,30.03,60.02)
    payload={
        "type":"FeatureCollection",
        "features":[
            {"type":"Feature","properties":{"aoi_id":"A"},"geometry":mapping(a)},
            {"type":"Feature","properties":{"aoi_id":"B"},"geometry":mapping(b)},
        ],
    }
    (tmp_path/"areas.geojson").write_text(json.dumps(payload),encoding="utf-8")
    parts=LocalDataset(tmp_path).intersecting_parents(query)
    assert [p.aoi_id for p,_ in parts]==["A","B"]
    assert parts[0][1].intersection(parts[1][1]).area==0
    summed=sum(geodesic_area_ha(g) for _,g in parts)
    assert abs(summed-geodesic_area_ha(query))/geodesic_area_ha(query)<1e-9
