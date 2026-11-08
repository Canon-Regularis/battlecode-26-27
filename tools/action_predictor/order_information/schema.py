"""Fixed, permutation-invariant relational order inputs; no policy rules."""
import numpy as np

PARTS=('available','count','min_delta','max_delta','mean_delta','below_fraction','equal_fraction','above_fraction')
FIELDS=tuple(f'{role}_{time}_{part}' for role in ('ally','enemy')
             for time in ('current','scheduled') for part in PARTS)


def encode(row):
    output=[]
    for role in ('ally','enemy'):
        for time in ('current','scheduled'):
            units=[u for u in row['others'] if u['known'] and u['role']==role and u[time+'_available']]
            values=np.asarray([u[time] for u in units],dtype=np.int64)
            own=row['own'][time]
            reference=row['own'][time+'_available']
            if not reference or not len(values):
                output.extend([0,len(values),0,0,0,0,0,0])
                continue
            if own is None:
                raise ValueError('Available priority lacks an integer value')
            delta=values-np.int64(own)
            output.extend([1,len(values),int(delta.min()),int(delta.max()),float(delta.mean()),
                           float((delta<0).mean()),float((delta==0).mean()),float((delta>0).mean())])
    result=np.asarray(output,dtype=np.float32)
    if result.shape!=(32,) or not np.isfinite(result).all():
        raise ValueError('Invalid order-feature representation')
    return result


def normalizer(raw_fit):
    x=np.asarray(raw_fit,dtype=np.float64)
    return x.mean(0).astype(np.float32),np.maximum(x.std(0,ddof=1),.01).astype(np.float32)
