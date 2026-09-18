import pytest
from carbon_mrv.carbon.baseline import BaselineTrajectory

def test_baseline_formula_and_floor():
    t=BaselineTrajectory("x",cbar_2015_tC_ha=40,cbar_2019_tC_ha=44)
    assert t.annual_slope_tC_ha==1; assert t.cbar(2021)==46
    assert t.emission(100,2020,2021)==pytest.approx(-100*1*44/12)
    falling=BaselineTrajectory("y",100,0); assert falling.cbar(2024)==0
