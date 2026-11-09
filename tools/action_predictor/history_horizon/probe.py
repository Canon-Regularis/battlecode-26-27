"""Bounded live-cache construction/likelihood proof without optimizer updates."""
import json
import numpy as np
import torch
from .data import load,legacy,input_batch,geometry,targets,chunks,INPUTS
from .model import Policy
from .engine import take,put,train_window
from .assessment import windows
from .protocol import REPORT,SEED
from ..reliable_train import setup
from ..audit import immutable_json


def run():
    setup(SEED);model=Policy();report={}
    for split in ('fit','tuning','assessment','legacy'):
        data=legacy() if split=='legacy' else load(split);raw=data['arrays']
        if np.any(raw['observations'][raw['history_gaps'][:,:,1]==0]):raise ValueError('Missing observation nonzero')
        if np.any(raw['priority_inputs'][:,:4]):raise ValueError('Current priority leaked')
        report[split]=dict(rows=len(raw['y']),streams=len(data['sequences']),groups=len(np.unique(data['group'])),
            windows16=len(windows(data,16)),windows32=len(windows(data,32)),input_keys=list(INPUTS))
        # No target-dependent quality measures on tuning/assessment before fit.
        if split not in ('fit','legacy'):continue
        checked=0;parity=0.;state=model.empty(32)
        with torch.no_grad():
            for rows in chunks(data['sequences'],unroll=32):
                for row in rows:
                    active=torch.from_numpy(np.flatnonzero(row>=0));ids=row[row>=0]
                    if not len(ids):continue
                    step=model.begin(**input_batch(data,ids),state=take(state,active),reset8=False)
                    geo=geometry(data,ids);p=model.decode(step,**geo)
                    mode_loss,_=model.observed(step,**geo,y=p['prediction'],py=p['proposed_coordinate'],priority=p['priority'])
                    difference=float((mode_loss+p['family_mode_logp'].max(-1).values).abs().max())
                    parity=max(parity,difference)
                    loss,post=model.observed(step,**geo,**targets(data,ids))
                    if not torch.isfinite(loss).all():raise ValueError('Nonfinite actual-cache likelihood')
                    state=put(state,active,post);checked+=len(ids)
                    if checked>=1536:break
                if checked>=1536:break
        if parity>1e-7:raise ValueError('Actual-cache decoder mismatch')
        report[split].update(causal_probe_rows=checked,max_decoder_nll_error=parity)
        if split=='fit':
            rows=next(chunks(data['sequences'],unroll=32));gradients={}
            for arm in ('A','B','C'):
                setup(SEED);m=Policy();train_window(m,data,rows,m.empty(32),arm)
                gradients[arm]=dict(finite=all(p.grad is None or bool(torch.isfinite(p.grad).all()) for p in m.parameters()),
                    nonzero_tensors=sum(p.grad is not None and bool(torch.count_nonzero(p.grad)) for p in m.parameters()))
            report[split]['backward_without_optimizer']=gradients
        print('Probed',split,report[split],flush=True)
    immutable_json(REPORT/'construction-probe.json',dict(partitions=report,new_fits=0,optimizer_updates=0,
        interpretation='Construction and causal/likelihood proof only; no movement quality or strategy conclusion.'))


if __name__=='__main__':run()
