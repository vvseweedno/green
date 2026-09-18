import math
from carbon_mrv.carbon.credits import calculate_potential_credits
from carbon_mrv.carbon.stock import CF, CO2_PER_C

def test_official_golden_example_q_395():
    area=100.0
    eproj=-(104-100)*CF*area*CO2_PER_C
    ebase=-(101-100)*CF*area*CO2_PER_C
    r=ebase-eproj; h=103.4
    out=calculate_potential_credits(area_ha=area,year_start=2020,year_end=2021,Ebase=ebase,Eproj=eproj,lower=eproj-h,upper=eproj+h)
    assert math.isclose(eproj,-689.3333333333333)
    assert math.isclose(ebase,-172.33333333333331)
    assert math.isclose(r,517.0)
    assert math.isclose(out.H_over_R,0.20)
    assert math.isclose(out.UNC,0.10)
    assert math.isclose(out.Radj,465.3)
    assert math.isclose(out.buffer,69.795)
    assert out.Q==395
