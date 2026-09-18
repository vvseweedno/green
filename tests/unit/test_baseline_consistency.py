from pathlib import Path

from carbon_mrv.data.local import LocalDataset


def test_baseline_consistency_report_accepts_formula_rows(tmp_path: Path):
    (tmp_path/"baseline.csv").write_text(
        "aoi_id,year,cbar\nA,2015,40\nA,2019,44\nA,2020,45\nA,2021,46\n",
        encoding="utf-8",
    )
    report=LocalDataset(tmp_path).baseline_consistency_report()
    assert report["status"]=="consistent"
    assert report["checked_values"]==4
    assert report["mismatch_count"]==0


def test_baseline_consistency_report_finds_mismatch(tmp_path: Path):
    (tmp_path/"baseline.csv").write_text(
        "aoi_id,year,cbar\nA,2015,40\nA,2019,44\nA,2020,99\n",
        encoding="utf-8",
    )
    report=LocalDataset(tmp_path).baseline_consistency_report()
    assert report["status"]=="mismatch"
    assert report["mismatch_count"]==1
    assert report["mismatches"][0]["year"]==2020
