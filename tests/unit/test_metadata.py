import json
from pathlib import Path

from carbon_mrv.data.metadata import MANDATORY_METADATA_FILES, load_official_metadata


def test_all_mandatory_metadata_are_ingested(tmp_path: Path):
    csv_names={"areas.csv","scenes.csv","events.csv","sources.csv","file_catalog.csv","baseline.csv","parameters.csv"}
    for name in MANDATORY_METADATA_FILES:
        path=tmp_path/name
        if name in csv_names:
            if name=="parameters.csv":
                path.write_text("parameter,value\nCF,0.47\n",encoding="utf-8")
            else:
                path.write_text("id,value\nx,1\n",encoding="utf-8")
        elif name=="sample_requests.geojson":
            path.write_text(json.dumps({"type":"FeatureCollection","features":[{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[]}}]}),encoding="utf-8")
        elif name=="areas.geojson":
            path.write_text(json.dumps({"type":"FeatureCollection","features":[]}),encoding="utf-8")
        else:
            path.write_text(json.dumps({"scene-x":{"processing_baseline":"05.11"}}),encoding="utf-8")
    out=load_official_metadata(tmp_path)
    assert out["missing"]==[]
    assert out["sample_request_count"]==1
    assert out["methodology_parameters"]["CF"]==0.47
    assert len(out["files"])==len(MANDATORY_METADATA_FILES)
