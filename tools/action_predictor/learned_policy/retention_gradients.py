"""Local TRAIN loss pressure on retention; frozen weights, no optimizer."""
import hashlib
import json
import sys
from collections import Counter
import numpy as np
import torch
from .sequence_data import BASE, WORK, REPORT, JOBS
from .data import load, causal_inputs, geometry, targets
from .model import GoalPolicy
from ..priority_fit_v3 import load_base
from .. import reliable_train as rt
from ..audit import immutable_json
from ..data import digest


def fingerprint(model):
    h=hashlib.sha256()
    for name,value in model.state_dict().items():h.update(name.encode());h.update(value.detach().numpy().tobytes())
    return h.hexdigest()


def plan():
    immutable_json(REPORT/'retention-gradient-plan.json',dict(
        purpose='Test local pressure of command NLL versus .05future-position auxiliary on the learned retention gate; no optimizer or new fit.',
        selection='Eligible TRAIN only: first6distinct groups per engine, first actor stream per chosen game, first64selected decisions. Probe first16available-goal noninitial known-position rows after8prefix decisions per stream. No action-label-based case selection.',
        checkpoints='Exact seed20261114 initial persistent model (unfitted), saved L01round1, selected L01checkpoint. Identical forward actual-action history per model; no backward-smoothed state.',
        derivative='Current-step partial gradients w.r.t. effective gap retention and retention bias, holding earlier state detached. Positive derivative means gradient descent would locally decrease retention. Auxiliary multiplied by frozen.05. Not the full8nodeBPTT gradient or a causal attribution of training trajectory.',
        interpretation='Future achieved position is a receding-horizon forecast target, not true persistent intent. Gradient evidence may support or reject a local forgetting-pressure hypothesis; do not infer that all persistent policies fail.',
        source_sha256=digest(__file__),new_fits=0,reserved_opened=0))


def run():
    plan();rt.setup(20261114);teacher,saved=load_base();model=GoalPolicy(teacher,True);model.eval();torch.set_num_threads(2)
    info=json.loads((REPORT/'L01.json').read_text());d=load('train',saved)
    jobs=json.loads(JOBS.read_text());chosen=[]
    for engine in ('2.0.0','3.0.0'):
        groups=set()
        for j in jobs:
            if j['split']!='train' or j['record']['engine_version']!=engine or j['record']['group'] in groups:continue
            groups.add(j['record']['group']);chosen.append(j)
            if len(groups)==6:break
        assert len(groups)==6
    streams=[]
    for j in chosen:
        stream=next(s for s in d['sequences'] if j['offset']<=s[0]<j['offset']+j['rows'])
        streams.append((j,stream[:64]))
    result={};records={};bindings={}
    checkpoints=[('initial',None),('round1',WORK/'runs/L01/round-01.pt'),('selected',WORK/f"runs/L01/round-{info['selected_round']:02d}.pt")]
    for label,path in checkpoints:
        if path is not None:
            model.load_state_dict(torch.load(path,weights_only=False)['state']);bindings[str(path)]=digest(path)
        before=fingerprint(model);rows=[];action_counts=Counter()
        for j,sequence in streams:
            state=model.empty(1);probes=0
            for at,row in enumerate(sequence):
                ix=np.array([row]);inputs=causal_inputs(d,ix);geo=geometry(d,ix)
                eligible=at>=8 and probes<16 and bool(d['goals']['goal_target_available'][row]) and bool(d['goals']['position_known'][row])
                with torch.set_grad_enabled(eligible):
                    step=model.begin(**inputs,state=state);target=targets(d,ix)
                    command,post=model.observed(step,**geo,**{k:target[k] for k in ('y','py','priority_parameter_nll')})
                    if eligible:
                        auxiliary=.05*model.achieved_goal_loss(step,target['achieved'],target['achievement_available'])
                        variables=(step['retain'],model.retention.bias)
                        cg=torch.autograd.grad(command.sum(),variables,retain_graph=True,allow_unused=True)
                        ag=torch.autograd.grad(auxiliary.sum(),variables,allow_unused=True)
                        def scalar(x):return float(x.detach().reshape(-1)[0]) if x is not None else 0.
                        rows.append(dict(row=int(row),engine=j['record']['engine_version'],group=j['record']['group'],
                            retention=float(step['retain'][0].detach()),command_nll=float(command[0].detach()),weighted_auxiliary=float(auxiliary[0].detach()),
                            command_d_effective_retention=scalar(cg[0]),auxiliary_d_effective_retention=scalar(ag[0]),
                            command_d_retention_bias=scalar(cg[1]),auxiliary_d_retention_bias=scalar(ag[1])))
                        probes+=1;action_counts[rt.LABELS[int(d['raw']['y'][row])]]+=1
                state={k:v.detach() for k,v in post.items()}
        assert fingerprint(model)==before
        fields={k:np.array([r[k] for r in rows]) for k in ('command_d_effective_retention','auxiliary_d_effective_retention','command_d_retention_bias','auxiliary_d_retention_bias')}
        result[label]=dict(rows=len(rows),actions=dict(action_counts),mean_retention=float(np.mean([r['retention'] for r in rows])),
            gradients={k:dict(mean=float(v.mean()),mean_absolute=float(np.abs(v).mean()),positive=int((v>0).sum()),negative=int((v<0).sum()),zero=int((v==0).sum())) for k,v in fields.items()},
            total_bias_gradient_decreases_retention=int(((fields['command_d_retention_bias']+fields['auxiliary_d_retention_bias'])>0).sum()),weights_unchanged=True)
        records[label]=rows;print('Retention local gradients',label,result[label],flush=True)
    artifact=WORK/'L01-retention-gradients.json';immutable_json(artifact,records)
    immutable_json(REPORT/'L01-retention-gradients.json',dict(results=result,artifact_sha256=digest(artifact),checkpoint_bindings=bindings,
        selected_groups=[dict(raw=j['record']['raw_sha256'],group=j['record']['group'],engine=j['record']['engine_version']) for j in chosen],
        input_receipt_sha256=digest(REPORT/'policy-input-bindings.json'),plan_sha256=digest(REPORT/'retention-gradient-plan.json'),source_sha256=digest(__file__),
        qualification='Bounded early-trajectory TRAIN local derivatives at frozen weights. Earlier state detached; not full training gradient, optimizer update, proof of information insufficiency or definitive cause of learned forgetting. Initial model is an arithmetic/loss probe, not a third fit.',
        new_fits=0,reserved_opened=0))


if __name__=='__main__':run()
