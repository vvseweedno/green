from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.ndimage import gaussian_filter
from carbon_mrv.carbon.stock import CF,CO2_PER_C

@dataclass(frozen=True)
class UncertaintyResult:
    central_E_tco2e:float; lower_tco2e:float; upper_tco2e:float; quantiles:tuple[float,float]
    simulations:int; temporal_rho:float; spatial_length_pixels:float; seed:int; scenario:str
    method:str="model-based correlated Monte Carlo"

def _field(rng:np.random.Generator,shape:tuple[int,...],sigma_pixels:float)->np.ndarray:
    z=rng.normal(size=shape)
    if sigma_pixels>0: z=gaussian_filter(z,sigma=sigma_pixels,mode="reflect")
    sd=float(np.std(z)); return z/sd if sd>0 else z

def simulate_stock_difference(*,agb0,agb1,sd0,sd1,area_ha,temporal_rho:float,spatial_length_pixels:float,simulations:int=500,seed:int=20260918,scenario:str="custom",quantiles:tuple[float,float]=(0.05,0.95))->UncertaintyResult:
    arrays=[np.asarray(x,dtype=float) for x in (agb0,agb1,sd0,sd1,area_ha)]; shape=arrays[0].shape
    if any(a.shape!=shape for a in arrays): raise ValueError("All uncertainty arrays must share a shape")
    if not -1<=temporal_rho<=1: raise ValueError("temporal_rho must be in [-1, 1]")
    if simulations<2: raise ValueError("simulations must be >= 2")
    b0,b1,s0,s1,area=arrays
    valid=np.isfinite(b0)&np.isfinite(b1)&np.isfinite(s0)&np.isfinite(s1)&np.isfinite(area)&(s0>=0)&(s1>=0)&(area>0)
    if not np.any(valid): raise ValueError("No valid uncertainty pixels")
    central_E=-float(np.sum(area[valid]*(b1[valid]-b0[valid])*CF))*CO2_PER_C
    rng=np.random.default_rng(seed); draws=np.empty(simulations,dtype=float); rho=float(temporal_rho); orth=float(np.sqrt(max(0.0,1.0-rho*rho)))
    for i in range(simulations):
        z0=_field(rng,shape,spatial_length_pixels); zi=_field(rng,shape,spatial_length_pixels); z1=rho*z0+orth*zi
        p0=b0+s0*z0; p1=b1+s1*z1
        draws[i]=-float(np.sum(area[valid]*(p1[valid]-p0[valid])*CF))*CO2_PER_C
    lo,hi=np.quantile(draws,quantiles)
    return UncertaintyResult(central_E,float(lo),float(hi),quantiles,simulations,rho,float(spatial_length_pixels),seed,scenario)

SCENARIOS={"independent":{"temporal_rho":0.0,"spatial_length_pixels":0.0},"moderate":{"temporal_rho":0.5,"spatial_length_pixels":1.5},"strong":{"temporal_rho":0.8,"spatial_length_pixels":3.0}}

def run_scenario(name:str,**kwargs)->UncertaintyResult:
    if name not in SCENARIOS: raise KeyError(f"Unknown uncertainty scenario: {name}")
    return simulate_stock_difference(scenario=name,**SCENARIOS[name],**kwargs)
