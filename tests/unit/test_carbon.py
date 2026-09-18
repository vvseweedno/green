import math
from carbon_mrv.carbon.stock import StockEstimate, annualized_emission_intensity, stock_difference_emission_tco2e, stock_from_weighted_pixels

def test_weighted_stock_keeps_zero_agb():
    s=stock_from_weighted_pixels([0.0,100.0],[1.0,1.0]); assert s.area_ha==2.0; assert math.isclose(s.total_carbon_t,47.0); assert math.isclose(s.mean_carbon_t_ha,23.5)

def test_sign_semantics_loss_is_positive_E():
    assert stock_difference_emission_tco2e(StockEstimate(10,100,10),StockEstimate(10,90,9))>0

def test_annualized_intensity():
    assert annualized_emission_intensity(100,10,2020,2022)==5
