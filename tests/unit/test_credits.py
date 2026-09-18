import math
import pytest
from carbon_mrv.carbon.credits import calculate_potential_credits

def call(**overrides):
    args=dict(area_ha=100,year_start=2020,year_end=2021,Ebase=100,Eproj=0,lower=-5,upper=5); args.update(overrides); return calculate_potential_credits(**args)

def test_r_non_positive_zeroes_q_and_ratio_null():
    out=call(Ebase=-1,Eproj=0); assert out.Q==0 and out.H_over_R is None
    out=call(Ebase=0,Eproj=0); assert out.Q==0 and out.H_over_R is None

def test_threshold_at_point_one_has_no_deduction():
    out=call(Ebase=100,Eproj=0,lower=-10,upper=10); assert out.H_over_R==pytest.approx(0.1); assert out.UNC==0

def test_ratio_one_zeroes_q():
    out=call(Ebase=100,Eproj=0,lower=-100,upper=100); assert out.H_over_R==1; assert out.Q==0

def test_partial_coverage_unavailable(): assert call(full_coverage=False).status=="unavailable"
def test_missing_baseline_unavailable(): assert call(baseline_available=False).status=="unavailable"

@pytest.mark.parametrize("value",[math.nan,math.inf,-math.inf])
def test_non_finite_unavailable(value): assert call(Eproj=value).status=="unavailable"

def test_non_positive_area_and_dt_unavailable():
    assert call(area_ha=0).status=="unavailable"; assert call(year_end=2020).status=="unavailable"
