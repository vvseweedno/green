import json
import os
from pathlib import Path

import pytest

from carbon_mrv.reporting.golden import default_golden_cases, run_golden_case

DATASET=Path(os.getenv("CARBON_MRV_DATASET","data/raw"))
FIXTURES=Path("tests/golden/fixtures")


def _assert_close(actual,expected,path="root"):
    if isinstance(expected,float):
        assert isinstance(actual,(int,float)),f"{path}: expected numeric"
        assert actual==pytest.approx(expected,rel=1e-9,abs=1e-9),path
        return
    if isinstance(expected,dict):
        assert isinstance(actual,dict),path
        assert set(actual)==set(expected),f"{path}: keys differ"
        for key in expected:
            _assert_close(actual[key],expected[key],f"{path}.{key}")
        return
    if isinstance(expected,list):
        assert isinstance(actual,list),path
        assert len(actual)==len(expected),f"{path}: list length differs"
        for idx,(a,e) in enumerate(zip(actual,expected,strict=True)):
            _assert_close(a,e,f"{path}[{idx}]")
        return
    assert actual==expected,path


@pytest.mark.skipif(not DATASET.exists(),reason="official dataset not mounted")
def test_real_data_golden_fixtures_when_frozen():
    manifest_path=FIXTURES/"manifest.json"
    if not manifest_path.exists():
        pytest.skip("real-data golden fixtures not frozen yet; run make freeze-golden after verification")
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    cases={case.name:case for case in default_golden_cases(DATASET)}
    for name in manifest["cases"]:
        fixture_path=FIXTURES/f"{name}.json"
        assert fixture_path.exists(),f"missing golden fixture {fixture_path}"
        expected=json.loads(fixture_path.read_text(encoding="utf-8"))
        actual=run_golden_case(
            cases[name],
            DATASET,
            simulations=int(manifest["simulations"]),
            seed=int(manifest["seed"]),
        )
        _assert_close(actual,expected,name)
