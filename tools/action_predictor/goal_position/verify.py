"""Parent verification, without optimizer updates or new model selection."""
import json,time
from collections import Counter,defaultdict
import numpy as np
import torch
from . import model
from .study import OUT,RUN,ROOT,check,load,evaluate,metrics
from ..audit import immutable_json
from ..data import digest


def run():
    torch.set_num_threads(4)
    plan=json.loads((OUT/'protocol.json').read_text());check(plan)
    result=json.loads((OUT/'result.json').read_text())
    for p,h in result['bindings'].items():
        if digest(ROOT/p)!=h:raise ValueError('Result archive changed')
    torch.manual_seed(plan['seed']);net=model.GoalMap(plan['schema'])
    initial=torch.load(RUN/'initial.pt',map_location='cpu',weights_only=True)
    assert all(torch.equal(v,initial[k]) for k,v in net.state_dict().items())
    saved=torch.load(RUN/'final.pt',map_location='cpu',weights_only=False);net.load_state_dict(saved['model'])
    assert all(torch.isfinite(v).all() for v in saved['model'].values())
    steps={int(v['step']) for v in saved['optimizer']['state'].values()};assert steps=={804}
    assert len(saved['optimizer']['state'])==len(list(net.parameters()))
    rng=np.random.default_rng(plan['seed']);trace=json.loads((RUN/'trace.json').read_text())
    assert len(trace)==plan['passes']
    for epoch,t in enumerate(trace,1):
        assert t['schedule']==rng.permutation(plan['rows']).tolist()
        assert sorted(t['schedule'])==list(range(plan['rows']))
        assert t['updates']==epoch*((plan['rows']+plan['batch_size']-1)//plan['batch_size'])
    verified={}
    for split in ('fit','evaluation'):
        recreated=evaluate(net,plan['schema'],split,plan['batch_size'],time.perf_counter()+300)
        archive=json.loads((RUN/(split+'-predictions.json')).read_text())
        assert recreated==archive,'Forecast/summary reproduction failed'
        assert recreated['summary']==result['summary'][split]
        verified[split]=len(recreated['model'])
    rows,targets,routes=load('fit');archive=json.loads((RUN/'fit-predictions.json').read_text())
    categories=defaultdict(list);self_targets=Counter()
    for y,r in zip(targets,archive['model']):
        categories[y['anchor_family']].append(r)
        if y['anchor_target']==dict(x=y['goal'][0],y=y['goal'][1]):self_targets[y['anchor_family']]+=1
    diagnostics={k:dict(**metrics(v),self_target_rows=self_targets[k]) for k,v in categories.items()}
    # Exercise deployment-shaped inference with only the current observation/supplement/map.
    from .predictor import GoalPredictor
    predictor=GoalPredictor();one=predictor.predict(rows[0]['observation'],rows[0]['supplement'],routes[targets[0]['payload']])
    assert list(one['goal'])==archive['model'][0]['goal']
    immutable_json(OUT/'verification.json',dict(result_sha256=digest(OUT/'result.json'),
        exact_initial_tensors=True,exact_schedules=True,finite_final_tensors=True,optimizer_steps=sorted(steps),
        recreated_rows=verified,full_forecasts_and_metrics_exact=True,current_only_inference_passed=True,
        fitting_anchor_diagnostics=diagnostics,optimizer_updates=0,subagents=False))
    print(json.dumps(dict(verified_rows=verified,fitting_anchor_diagnostics=diagnostics),indent=2))


if __name__=='__main__':run()
