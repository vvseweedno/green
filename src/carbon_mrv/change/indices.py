from __future__ import annotations
import numpy as np

def normalized_difference(a,b,eps:float=1e-8):
    a=np.asarray(a,dtype=float); b=np.asarray(b,dtype=float); den=a+b
    out=np.full(np.broadcast_shapes(a.shape,b.shape),np.nan,dtype=float)
    valid=np.isfinite(a)&np.isfinite(b)&(np.abs(den)>eps)
    np.divide(a-b,den,out=out,where=valid); return out

def ndvi(b8a,b04): return normalized_difference(b8a,b04)
def nbr(b8a,b12): return normalized_difference(b8a,b12)
def ndmi(b8a,b11): return normalized_difference(b8a,b11)

def scene_indices(scene):
    return {"NDVI":ndvi(scene["B8A"],scene["B04"]),"NBR":nbr(scene["B8A"],scene["B12"]),"NDMI":ndmi(scene["B8A"],scene["B11"])}
