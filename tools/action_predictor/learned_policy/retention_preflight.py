"""Actual eight-node TRAIN gradient contract; no optimizer or parameter update."""
import copy
import json
import numpy as np
import torch
from .sequence_data import WORK, REPORT
from .model import GoalPolicy
from .data import load, chunks, causal_inputs, geometry, targets
from .inference import select_state
from .retention_routing import backward
from .retention_protocol import freeze
from .retention_gradients import fingerprint
from ..priority_fit_v3 import load_base
from .. import reliable_train as rt
from ..audit import immutable_json
from ..data import digest


def run():
    freeze(); rt.setup(20261114); teacher,saved=load_base()
    model=GoalPolicy(teacher,True); reference=copy.deepcopy(model)
    initial=fingerprint(model); assert initial==fingerprint(reference)
    d=load('train',saved); state=model.empty(2); oldstate=reference.empty(2)
    losses=[]; auxiliary=[]; count=0; cases=[]
    rows=next(chunks(d['sequences'],np.random.default_rng(20261114),batch_size=2,unroll=8))
    for ids in rows:
        valid=ids>=0; ix=np.maximum(ids,0); mask=torch.from_numpy(valid)
        inputs=causal_inputs(d,ix); geo=geometry(d,ix); target=targets(d,ix)
        step=model.begin(**inputs,state=state)
        with torch.no_grad():
            control=reference.begin(**inputs,state=oldstate)
            for key in step: torch.testing.assert_close(step[key],control[key],rtol=0,atol=0)
            _,post0=reference.observed(control,**geo,**{k:target[k] for k in ('y','py','priority_parameter_nll')})
            oldstate=select_state(oldstate,post0,mask)
        loss,post=model.observed(step,**geo,**{k:target[k] for k in ('y','py','priority_parameter_nll')})
        aux=model.achieved_goal_loss(step,target['achieved'],target['achievement_available'])
        losses.append(loss[mask].sum()); auxiliary.append(aux[mask].sum())
        count+=int(valid.sum()); cases.extend(ids[valid].tolist())
        state=select_state(state,post,mask)
    primary=torch.stack(losses).sum()/count; aux=torch.stack(auxiliary).sum()/count
    named=[(n,p) for n,p in model.named_parameters() if p.requires_grad]
    params=[p for _,p in named]; total=torch.autograd.grad(primary+.05*aux,params,retain_graph=True,allow_unused=True)
    command=torch.autograd.grad(primary,params,retain_graph=True,allow_unused=True)
    auxgrad=torch.autograd.grad(.05*aux,params,retain_graph=True,allow_unused=True)
    backward(model,primary,aux)
    diagnostics={}; changed=[]
    for (name,p), combined,cg,ag in zip(named,total,command,auxgrad):
        expected=cg if name.startswith('retention.') else combined
        if expected is None: assert p.grad is None,name
        else: torch.testing.assert_close(p.grad,expected,rtol=0,atol=0)
        if ag is not None and bool((ag!=0).any()): changed.append(name)
        if name.startswith('retention.'):
            assert cg is not None and ag is not None
            diagnostics[name]=dict(command_norm=float(cg.norm()),excluded_weighted_aux_norm=float(ag.norm()),routed_norm=float(p.grad.norm()))
    assert 'retention.bias' in changed and diagnostics['retention.bias']['command_norm']>0
    assert any(n.startswith('goal_prediction.') for n in changed)
    assert any(not n.startswith(('retention.','goal_prediction.')) for n in changed)
    assert fingerprint(model)==initial
    immutable_json(REPORT/'L02-gradient-preflight.json',dict(
        rows=cases,unroll_nodes=len(rows),graph='Actual eligible TRAIN eight-node recurrent window, earlier state NOT detached within window; no optimizer.',
        identical_forward_and_initial_state=True,initial_state_fingerprint=initial,
        retention=diagnostics,other_auxiliary_gradient_parameters=changed,
        all_other_gradients_exactly_equal_original_combined_objective=True,
        retention_gradients_exactly_equal_command_only=True,weights_unchanged=True,
        protocol_sha256=digest(REPORT/'L02-protocol.json'),source_sha256=digest(__file__),new_fits=0,reserved_opened=0))
    print('L02 eight-node gradient and forward parity preflight passed',diagnostics,flush=True)


if __name__=='__main__':run()
