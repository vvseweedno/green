from pathlib import Path

from carbon_mrv.reporting.report import write_report


def test_report_contains_self_contained_map_and_audit_sections(tmp_path: Path):
    result={
        "run_id":"test-run",
        "created_at_utc":"2026-09-18T00:00:00Z",
        "request":{
            "geometry":{
                "type":"Polygon",
                "coordinates":[[[30.0,60.0],[30.1,60.0],[30.1,60.1],[30.0,60.1],[30.0,60.0]]],
            },
            "year_start":2020,
            "year_end":2022,
        },
        "coverage":{
            "requested_area_ha":100.0,
            "computed_area_ha":100.0,
            "coverage_ratio":1.0,
            "missing_area_ha":0.0,
        },
        "stock":{
            "start":{"total_carbon_t":1000.0},
            "end":{"total_carbon_t":900.0},
            "delta_c_t":-100.0,
            "E_tco2e":366.6666667,
            "e_tco2e_ha_year":1.8333333,
            "yearly":[
                {"year":2019,"mean_carbon_t_ha":10.0},
                {"year":2020,"mean_carbon_t_ha":9.8},
                {"year":2021,"mean_carbon_t_ha":9.2},
                {"year":2022,"mean_carbon_t_ha":9.0},
            ],
        },
        "uncertainty":{"L":300.0,"U":430.0,"method":"scenario"},
        "credits":{"status":"available","Q":12},
        "events":[{
            "event_id":"chg-1",
            "direction":"disturbance",
            "area_ha":4.0,
            "confidence":"confirmed",
            "cause":None,
            "date_min":"2021-01-01",
            "date_max":"2021-12-31",
            "date_precision":"year_interval",
            "geometry":{
                "type":"Polygon",
                "coordinates":[[[30.02,60.02],[30.04,60.02],[30.04,60.04],[30.02,60.04],[30.02,60.02]]],
            },
            "evidence":[],
            "data_quality":[],
            "carbon_contribution":{"E_event_tco2e":25.0},
        }],
        "provenance":{"processing_config_hash":"abc"},
        "limitations":["test limitation"],
    }
    html_path,json_path=write_report(result,tmp_path)
    page=html_path.read_text(encoding="utf-8")
    assert json_path.exists()
    assert "AOI &amp; change-object map" in page or "AOI & change-object map" in page
    assert "chg-1" in page
    assert "<svg" in page
    assert "WGS84 extent" in page
    assert "Provenance" in page
