"""Same windows and eight-root recurrence; only optimizer cadence changes."""
import torch
from ..history_horizon.engine import train_window


ARMS={'U00':32,'U01':8}


def update_window(model,data,rows,optimizer,arm):
    if rows.shape!=(32,32) or (rows<0).any():raise ValueError('Full32by32 window required')
    state=model.empty(32);total=0.;records=[];width=ARMS[arm]
    for start in range(0,32,width):
        optimizer.zero_grad(set_to_none=True)
        state,loss,denominator=train_window(model,data,rows[start:start+width],state,'A')
        if denominator!=width*32:raise ValueError('Optimizer denominator changed')
        norm=torch.nn.utils.clip_grad_norm_(model.parameters(),5,error_if_nonfinite=True)
        optimizer.step()
        total+=loss;records.append(dict(rows=denominator,loss_sum=loss,preclip_norm=float(norm),clipped=bool(norm>5)))
    return total,records
