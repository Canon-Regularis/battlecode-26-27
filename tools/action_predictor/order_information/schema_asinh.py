"""Monotone signed-gap compression chosen from TRAIN range, before fitting."""
import numpy as np
from .schema import normalizer

PARTS=('available','count','min_asinh_delta','max_asinh_delta','mean_asinh_delta',
       'below_fraction','equal_fraction','above_fraction')
FIELDS=tuple(f'{role}_{time}_{part}' for role in ('ally','enemy')
             for time in ('current','scheduled') for part in PARTS)


def encode(row):
    output=[]
    for role in ('ally','enemy'):
        for time in ('current','scheduled'):
            values=np.asarray([u[time] for u in row['others']
                if u['known'] and u['role']==role and u[time+'_available']],dtype=np.int64)
            if not row['own'][time+'_available'] or not len(values):
                output.extend([0,len(values),0,0,0,0,0,0]);continue
            delta=values-np.int64(row['own'][time])
            compressed=np.arcsinh(delta.astype(np.float64))
            output.extend([1,len(values),float(compressed.min()),float(compressed.max()),float(compressed.mean()),
                float((delta<0).mean()),float((delta==0).mean()),float((delta>0).mean())])
    result=np.asarray(output,dtype=np.float32)
    if result.shape!=(32,) or not np.isfinite(result).all():raise ValueError('Invalid compressed order input')
    return result
