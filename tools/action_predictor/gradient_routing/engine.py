"""Project two coordinate gradients once per unchanged optimizer window."""
import numpy as np
import torch
from ..history_horizon.data import input_batch, geometry, targets
from ..history_horizon.engine import detach
from ..segment_policy.model import SPATIAL
from ..segment_policy.history_model import encode_command
from ..reliable_model import priority_log_mass

ARMS = {'R00': False, 'R01': True}


def observed_parts(model, step, geo, target, direction):
    """Same observed likelihood and assimilation, with disjoint loss terms."""
    y, py, priority = (target[k] for k in ('y', 'py', 'priority'))
    typ = -model.execution.action(step['context']).double().log_softmax(-1)[torch.arange(len(y)), y]
    coordinate = torch.zeros_like(typ)
    spatial = torch.isin(y, torch.tensor(SPATIAL))
    if spatial.any():
        lp = model.spatial(dict(context=step['context'][spatial]),
            **{k:v[spatial] for k,v in geo.items()}, family=y[spatial])
        coordinate = coordinate.index_copy(0, torch.where(spatial)[0], -lp[torch.arange(int(spatial.sum())), py[spatial]])
    integer = y == 9
    extra = torch.zeros_like(typ)
    if integer.any():
        mass = priority_log_mass(model.execution.priority(step['context'][integer]).double(), priority[integer].double())
        extra = extra.index_copy(0, torch.where(integer)[0], -mass)
    change = (y == 8) & (direction == 3)
    continuation = (y == 8) & (direction == 2)
    # None avoids manufacturing gradient paths when a stratum is absent.
    losses = [coordinate[change].sum() if change.any() else None,
              coordinate[continuation].sum() if continuation.any() else None,
              typ.sum() + coordinate[~(change | continuation)].sum() + extra.sum()]
    hidden = model.memory(torch.cat((step['base'], encode_command(y, py, priority)), -1), step['hidden'])
    return typ + coordinate + extra, losses, dict(hidden=hidden, age=step['age']+1)


def combine(gradients, project):
    """Simultaneous symmetric projection, using the two original vectors."""
    change, continuation, rest = gradients
    d, c = change.double(), continuation.double()
    dot = torch.dot(d, c); dn = torch.dot(d, d); cn = torch.dot(c, c)
    conflict = bool(dot < 0 and dn > 0 and cn > 0)
    ordinary = change + continuation + rest
    if project and conflict:
        routed = (rest.double() + (d-dot*c/cn) + (c-dot*d/dn)).to(rest.dtype)
    else:
        routed = ordinary
    if not torch.isfinite(routed).all():raise ValueError('Nonfinite routed gradient')
    return routed, dict(dot=float(dot),change_norm=float(dn.sqrt()),continue_norm=float(cn.sqrt()),
        rest_norm=float(rest.double().norm()),cosine=float(dot/(dn*cn).sqrt()) if dn>0 and cn>0 else None,
        conflict=conflict,projected=bool(project and conflict),ordinary_norm=float(ordinary.double().norm()),
        routed_norm=float(routed.double().norm()),routing_delta_norm=float((routed-ordinary).double().norm()))


def gradients(model, data, rows):
    """Accumulate three gradients over four detached eight-root segments."""
    rows = trim_rows(rows)
    if not 1 <= rows.shape[1] <= 32:
        raise ValueError('Complete 32-root windows, with 1..32 lanes, required')
    params = list(model.parameters());size = sum(p.numel() for p in params)
    vectors = [torch.zeros(size) for _ in range(3)];used = [False]*len(params)
    denominator = rows.size;state = model.empty(rows.shape[1]);total = 0.;totals = [0.,0.,0.]
    pending = [[],[],[]]
    for t, ids in enumerate(rows):
        step = model.begin(**input_batch(data,ids),state=state,reset8=True)
        target = targets(data,ids)
        loss, parts, state = observed_parts(model,step,geometry(data,ids),target,
            torch.from_numpy(data['arrays']['direction'][ids]))
        if not torch.isfinite(loss).all():raise ValueError('Nonfinite observed loss')
        total += float(loss.detach().sum())
        for i,part in enumerate(parts):
            if part is not None:pending[i].append(part);totals[i]+=float(part.detach())
        if (t+1)%8 == 0:
            active = [i for i in range(3) if pending[i]]
            for position,i in enumerate(active):
                g = torch.autograd.grad(torch.stack(pending[i]).sum()/denominator, params,
                    allow_unused=True, retain_graph=position+1<len(active))
                offset = 0
                for j,(p,v) in enumerate(zip(params,g)):
                    if v is not None:
                        vectors[i][offset:offset+p.numel()].add_(v.detach().reshape(-1));used[j]=True
                    offset += p.numel()
            pending = [[],[],[]];state = detach(state)
    if not np.isclose(sum(totals),total,atol=1e-8,rtol=1e-12):raise ValueError('Loss partition mismatch')
    return vectors,used,total,totals


def trim_rows(rows):
    if rows.ndim != 2 or rows.shape[0] != 32 or not 1 <= rows.shape[1] <= 32:
        raise ValueError('Complete 32-root windows, with 1..32 lanes, required')
    active = (rows >= 0).any(0)
    if not active.any() or (rows[:,active] < 0).any():
        raise ValueError('Partial or empty window')
    return rows[:,active]


def update_window(model,data,rows,optimizer,arm):
    project = ARMS[arm]
    rows = trim_rows(rows)
    optimizer.zero_grad(set_to_none=True)
    vectors,used,total,totals = gradients(model,data,rows)
    routed,record = combine(vectors,project)
    offset = 0
    for p,present in zip(model.parameters(),used):
        p.grad = routed[offset:offset+p.numel()].reshape_as(p).clone() if present else None
        offset += p.numel()
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(),5,error_if_nonfinite=True)
    optimizer.step()
    record.update(rows=int(rows.size),loss_sum=total,loss_parts=totals,preclip_norm=float(norm),clipped=bool(norm>5))
    return total,[record]
