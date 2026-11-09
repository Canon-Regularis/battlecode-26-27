"""Same 32-node optimizer denominator; only state reset/detachment differs."""
import numpy as np
import torch
from .data import input_batch,geometry,targets,chunks

ARMS={'A':dict(reset8=True,detach=8),'B':dict(reset8=False,detach=8),'C':dict(reset8=False,detach=32)}


def take(state,active):return {k:v[active] for k,v in state.items()}
def put(state,active,post):return {k:v.index_copy(0,active,post[k]) for k,v in state.items()}
def detach(state):return {k:v.detach() for k,v in state.items()}


def train_window(model,data,rows,state,arm):
    """Accumulate gradients, but never step the optimizer inside a window."""
    settings=ARMS[arm];denominator=int((rows>=0).sum());pending=[];total=0.
    for t,row in enumerate(rows):
        active=torch.from_numpy(np.flatnonzero(row>=0));ids=row[row>=0]
        if len(ids):
            step=model.begin(**input_batch(data,ids),state=take(state,active),reset8=settings['reset8'])
            loss,post=model.observed(step,**geometry(data,ids),**targets(data,ids))
            if not torch.isfinite(loss).all():raise ValueError('Nonfinite training loss')
            state=put(state,active,post);pending.append(loss.sum());total+=float(loss.detach().sum())
        if (t+1)%settings['detach']==0 or t+1==len(rows):
            if pending:(torch.stack(pending).sum()/denominator).backward()
            pending=[];state=detach(state)
    return state,total,denominator


@torch.no_grad()
def infer(model,data,arm,decode=False):
    model.eval();n=len(data['arrays']['y']);seen=np.zeros(n,np.uint8)
    result={'nll':np.full(n,np.nan)};state=model.empty(32)
    if decode:
        result.update({k:np.full(n,-1,np.int64) for k in ('prediction','coordinate','proposed_coordinate','priority')})
    for rows in chunks(data['sequences'],unroll=32):
        for row in rows:
            active=torch.from_numpy(np.flatnonzero(row>=0));ids=row[row>=0]
            if not len(ids):continue
            step=model.begin(**input_batch(data,ids),state=take(state,active),reset8=ARMS[arm]['reset8'])
            geo=geometry(data,ids)
            # Forecast before current labels are loaded or assimilated.
            if decode:p=model.decode(step,**geo)
            target=targets(data,ids);loss,post=model.observed(step,**geo,**target)
            state=put(state,active,post);result['nll'][ids]=loss.numpy();seen[ids]+=1
            if decode:
                for k in ('prediction','proposed_coordinate','priority'):result[k][ids]=p[k].numpy()
                result['coordinate'][ids]=p['family_coordinates'][torch.arange(len(ids)),target['y']].numpy()
    if not np.all(seen==1) or not np.isfinite(result['nll']).all():raise ValueError('Incomplete inference')
    return result


def selectors(data,forecast):
    raw=data['arrays'];nll=forecast['nll'];means=[]
    for direction in (2,3):
        mask=(raw['y']==8)&(raw['direction']==direction)
        if not mask.any():raise ValueError('Missing tuning movement stratum')
        means.append(float(nll[mask].mean()))
    return dict(movement=sum(means)/2,full=float(nll.mean()))
