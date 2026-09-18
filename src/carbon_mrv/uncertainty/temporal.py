from __future__ import annotations
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class TemporalRhoDiagnostic:
    median:float; q25:float; q75:float; outside_physical_fraction:float; n:int

def implicit_rho(sd0,sd1,sd_delta,eps:float=1e-12)->TemporalRhoDiagnostic:
    a=np.asarray(sd0,dtype=float); b=np.asarray(sd1,dtype=float); d=np.asarray(sd_delta,dtype=float)
    valid=np.isfinite(a)&np.isfinite(b)&np.isfinite(d)&(a>eps)&(b>eps)&(d>=0)
    raw=(a[valid]**2+b[valid]**2-d[valid]**2)/(2*a[valid]*b[valid])
    if raw.size==0: raise ValueError("No valid pixels for temporal rho diagnostic")
    outside=float(np.mean((raw<-1)|(raw>1))); clipped=np.clip(raw,-1.0,1.0); q25,med,q75=np.quantile(clipped,[0.25,0.5,0.75])
    return TemporalRhoDiagnostic(float(med),float(q25),float(q75),outside,int(raw.size))
