from __future__ import annotations
import numpy as np

def robust_annual_composite(index_scenes:list[dict[str,np.ndarray]],valid_masks:list[np.ndarray]):
    if not index_scenes or len(index_scenes)!=len(valid_masks):
        raise ValueError("index_scenes and valid_masks must be non-empty and aligned")
    names=tuple(index_scenes[0]); result={}; count=np.zeros_like(valid_masks[0],dtype=np.uint16)
    for mask in valid_masks: count += np.asarray(mask,dtype=bool)
    for name in names:
        stack=[]
        for scene,mask in zip(index_scenes,valid_masks,strict=True):
            arr=np.asarray(scene[name],dtype=float).copy(); arr[~np.asarray(mask,dtype=bool)]=np.nan; stack.append(arr)
        with np.errstate(all="ignore"): result[name]=np.nanmedian(np.stack(stack,axis=0),axis=0)
    result["valid_observation_count"]=count; return result
