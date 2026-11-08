"""Same full-row likelihood, eight-root resets and one update per window batch."""
import numpy as np
import torch
from ..gradient_routing.engine import trim_rows
from ..history_horizon.data import input_batch,geometry,targets
from ..history_horizon.engine import detach

ARMS={'N00':False,'N01':True}


def update_window(model,data,rows,optimizer,arm):
    if model.use_neighborhood!=ARMS[arm]:raise ValueError('Wrong arm interface')
    rows=trim_rows(rows);denominator=rows.size;state=model.empty(rows.shape[1])
    optimizer.zero_grad(set_to_none=True);pending=[];total=0.;movement_rows=0
    for t,ids in enumerate(rows):
        step=model.begin(**input_batch(data,ids),state=state,reset8=True)
        target=targets(data,ids);movement_rows+=int((target['y']==8).sum())
        loss,state=model.observed(step,**geometry(data,ids),**target)
        if not torch.isfinite(loss).all():raise ValueError('Nonfinite original likelihood')
        pending.append(loss.sum());total+=float(loss.detach().sum())
        if (t+1)%8==0:
            objective=torch.stack(pending).sum()/denominator
            if objective.requires_grad:objective.backward()
            pending=[];state=detach(state)
    parameters=model.trainable_parameters();active=any(p.grad is not None for p in parameters)
    norm=torch.nn.utils.clip_grad_norm_(parameters,5,error_if_nonfinite=True)
    optimizer.step()
    return total,[dict(rows=int(denominator),movement_rows=movement_rows,loss_sum=total,
        preclip_norm=float(norm),clipped=bool(norm>5),active=active)]
