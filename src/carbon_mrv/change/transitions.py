from __future__ import annotations
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class TransitionResult:
    dNBR:np.ndarray; dNDVI:np.ndarray; dNDMI:np.ndarray; score:np.ndarray
    disturbance:np.ndarray; recovery:np.ndarray; low_confidence:np.ndarray

def robust_z(values:np.ndarray,eps:float=1e-6)->np.ndarray:
    arr=np.asarray(values,dtype=float); med=np.nanmedian(arr); mad=np.nanmedian(np.abs(arr-med)); scale=max(1.4826*mad,eps)
    return (arr-med)/scale

def transition_maps(before,after,*,z_threshold:float=2.5,min_index_agreement:int=2,min_observations:int=1):
    d={name:np.asarray(before[name],dtype=float)-np.asarray(after[name],dtype=float) for name in ("NBR","NDVI","NDMI")}
    z={name:robust_z(d[name]) for name in d}
    loss_votes=sum((z[name]>=z_threshold).astype(np.uint8) for name in z)
    gain_votes=sum((z[name]<=-z_threshold).astype(np.uint8) for name in z)
    score=(z["NBR"]+z["NDVI"]+z["NDMI"])/3.0
    c0=np.asarray(before.get("valid_observation_count",np.ones_like(score)),dtype=float)
    c1=np.asarray(after.get("valid_observation_count",np.ones_like(score)),dtype=float)
    observable=(c0>=min_observations)&(c1>=min_observations)
    disturbance=observable&(loss_votes>=min_index_agreement); recovery=observable&(gain_votes>=min_index_agreement)
    low=~observable|(~disturbance&~recovery&(np.abs(score)>=z_threshold))
    return TransitionResult(d["NBR"],d["NDVI"],d["NDMI"],score,disturbance,recovery,low)
