import numpy as np
from carbon_mrv.uncertainty.monte_carlo import simulate_stock_difference
from carbon_mrv.uncertainty.temporal import implicit_rho

def test_correlated_monte_carlo_is_seed_deterministic():
    shape=(5,5); kwargs=dict(agb0=np.full(shape,100.0),agb1=np.full(shape,95.0),sd0=np.full(shape,10.0),sd1=np.full(shape,10.0),area_ha=np.ones(shape),temporal_rho=0.5,spatial_length_pixels=1.0,simulations=50,seed=42)
    a=simulate_stock_difference(**kwargs); b=simulate_stock_difference(**kwargs)
    assert a==b; assert a.lower_tco2e<=a.central_E_tco2e<=a.upper_tco2e

def test_implicit_rho_recovers_known_case():
    d=implicit_rho(np.array([10.0,10.0]),np.array([10.0,10.0]),np.array([10.0,10.0]))
    assert d.median==0.5; assert d.outside_physical_fraction==0
