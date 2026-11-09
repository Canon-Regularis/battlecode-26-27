"""Direct gate/decay-age diagnostics correcting L01 review findings, no fit."""
import json
import sys
import numpy as np
import torch
import torch.nn.functional as F
from .sequence_data import ROOT, BASE, WORK, REPORT
from .model import GoalPolicy
from .data import load, chunks, causal_inputs, geometry, targets
from .inference import select_state
from ..priority_fit_v3 import load_base
from ..audit import immutable_json
from ..data import digest


@torch.no_grad()
def run(identifier, split):
    torch.set_num_threads(2)
    info=json.loads((REPORT/f'{identifier}.json').read_text())
    checkpoint=WORK/f"runs/{identifier}/round-{info['selected_round']:02d}.pt"
    assert digest(checkpoint)==info['checkpoint_sha256']
    teacher,saved=load_base();model=GoalPolicy(teacher,True)
    model.load_state_dict(torch.load(checkpoint,weights_only=False)['state']);model.eval()
    d=load(split,saved);n=len(d['raw']['y']);state=model.empty(32)
    arrays={key:np.zeros(n,np.float32) for key in ('per_root_gate','log_per_root_gate','decay_age','effective_retention')}
    arrays.update(initial=np.zeros(n,bool),world_held_without_current_position=np.zeros(n,bool))
    captured=[]
    hook=model.retention.register_forward_hook(lambda layer,args,output:captured.append(output[:,0].detach()))
    seen=np.zeros(n,np.uint8)
    with np.load(WORK/f'runs/{identifier}/{split}-goals.npz') as z:
        archived_retention=z['retention']; archived_world=z['world']
    max_world_difference=0.; max_retention_difference=0.
    try:
        for rows in chunks(d['sequences']):
            for ids in rows:
                valid=ids>=0;ix=np.maximum(ids,0);mask=torch.from_numpy(valid)
                inputs=causal_inputs(d,ix);step=model.begin(**inputs,state=state)
                assert len(captured)==1;logit=captured.pop()
                initial=inputs['transition_gap'][:,2]>.5
                held=(~initial)&(~inputs['position_known'])&state['known'].any(1)
                if held.any():torch.testing.assert_close(step['world'][held],state['world'][held],rtol=0,atol=0)
                values=dict(per_root_gate=logit.sigmoid(),log_per_root_gate=F.logsigmoid(logit),
                    decay_age=step['age'][:,0],effective_retention=step['retain'],initial=initial,
                    world_held_without_current_position=held)
                for key,value in values.items():arrays[key][ids[valid]]=value.numpy()[valid]
                if valid.any():max_world_difference=max(max_world_difference,float(np.abs(step['world'].numpy()[valid]-archived_world[ids[valid]]).max()))
                if valid.any():max_retention_difference=max(max_retention_difference,float(np.abs(step['retain'].numpy()[valid]-archived_retention[ids[valid]]).max()))
                target=targets(d,ix)
                _,post=model.observed(step,**geometry(d,ix),**{k:target[k] for k in ('y','py','priority_parameter_nll')})
                state=select_state(state,post,mask);seen[ids[valid]]+=1
    finally:hook.remove()
    assert np.all(seen==1) and max_world_difference==0 and max_retention_difference==0
    masks={'all':np.ones(n,bool)}
    if split=='train':masks['natural']=np.load(BASE.parent/'v9/frequency/natural-mask.npy')
    def quantiles(x):return np.quantile(x,[0,.25,.5,.75,.95,1]).tolist() if len(x) else None
    results={}
    for label,m in masks.items():
        noninitial=m&~arrays['initial'];underflow=noninitial&(arrays['effective_retention']==0)
        results[label]=dict(rows=int(m.sum()),noninitial=int(noninitial.sum()),
            direct_per_root_gate_quantiles=quantiles(arrays['per_root_gate'][noninitial]),
            direct_log_per_root_gate_quantiles=quantiles(arrays['log_per_root_gate'][noninitial]),
            effective_retention_quantiles=quantiles(arrays['effective_retention'][m]),
            exact_decay_age_feature_quantiles=quantiles(arrays['decay_age'][m]),
            zero_effective_retention_noninitial=int(underflow.sum()),
            direct_gates_where_effective_underflowed=quantiles(arrays['per_root_gate'][underflow]),
            world_held_without_current_position=int((m&arrays['world_held_without_current_position']).sum()))
    path=WORK/f'runs/{identifier}/{split}-direct-memory.npz';assert not path.exists();np.savez_compressed(path,**arrays)
    immutable_json(REPORT/f'{identifier}-{split}-direct-memory.json',dict(results=results,
        artifact_sha256=digest(path),checkpoint_sha256=digest(checkpoint),
        archived_goals_sha256=digest(WORK/f'runs/{identifier}/{split}-goals.npz'),
        input_receipt_sha256=digest(REPORT/'policy-input-bindings.json'),source_sha256=digest(__file__),
        archived_world_max_difference=max_world_difference,archived_retention_max_difference=max_retention_difference,
        qualification='Direct sigmoid/logsigmoid before gap exponentiation, no inversion of underflowed effective retention. Exact forward decay-age feature is not the lifetime of all recurrent information: absent current position can preserve old world coordinates with blend1, and old memory also reaches new forecasts through attention. Initial-row gate is unused; direct per-root summaries exclude it. TRAIN in-sample, original augmented traversal.',
        new_fits=0,reserved_opened=0))
    print(identifier,split,'direct memory',results,flush=True)


if __name__=='__main__':run(*sys.argv[1:])
