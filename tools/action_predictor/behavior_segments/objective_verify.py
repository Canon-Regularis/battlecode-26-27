"""Reproduce objective supervision, selection, and causal adaptive inference."""
import time,json
from pathlib import Path
import numpy as np
import torch
from . import objective_experiment as fit,objective_assessment as assessment
from .objective_predictor import ObjectivePredictor
from ..audit import immutable_json
from ..data import digest


def run():
    start=time.perf_counter();p,parent,architecture,cache,ids=fit.inputs();fit.check(fit.read(fit.REPORT/'fit.json'));torch.set_num_threads(1)
    windows,maps=fit.base.heading.expanded.read();history,bound=fit.audit.prior_moves(windows)
    assert bound==fit.read(fit.REPORT/'audit.json')['source_bindings']
    rows=json.loads(json.dumps(fit.examples(windows,maps,history,ids)));assert rows==fit.read(fit.WORK/'rows.json')
    d=torch.load(fit.WORK/'targets.pt',weights_only=True);y=d['target'];ri=d['row'].tolist();assert y.tolist()==torch.tensor([c['utility'] for r in rows for c in r['candidates']]).tolist()
    assert ri==[i for i,r in enumerate(rows) for c in r['candidates']]
    scores={};accounting={}
    for name in ['fold0','fold1','fold2','fold3','full']:
        all_x=fit.prior.cached_features(name,parent,architecture,cache)[...,:56]
        x=torch.stack([torch.cat((all_x[r['window'],r['position']],torch.tensor(c['features']))) for r in rows for c in r['candidates']])
        assert torch.equal(x,torch.load(fit.WORK/(name+'.pt'),weights_only=True));net=fit.new(p)
        folder=fit.WORK/name if name!='full' else fit.WORK/'refit';initial=torch.load(folder/'initial.pt',weights_only=True)
        assert all(torch.equal(v,initial[k]) for k,v in net.state_dict().items())
        if name=='full':indices=np.arange(len(y));held=None
        else:
            fold=int(name[-1]);indices=np.array([i for i,r in enumerate(ri) if rows[r]['fold']!=fold]);held=np.array([i for i,r in enumerate(ri) if rows[r]['fold']==fold and rows[r]['canonical']])
        rng=np.random.default_rng(p['seed']);trace=fit.read(folder/'trace.json');updates=0
        for e in trace:
            assert rng.permutation(indices).tolist()==e['order'] and np.isfinite(e['norms']).all()
            assert len(e['norms'])==(len(indices)+p['batch']-1)//p['batch'];updates+=len(e['norms'])
            if e.get('held_sum') is not None:
                net.load_state_dict(torch.load(folder/f"epoch-{e['epoch']:03d}.pt",weights_only=True))
                with torch.no_grad():value=float((net(x[held])-y[held]).square().double().sum())
                assert value==e['held_sum'];scores.setdefault(e['epoch'],[]).append((value,len(held)))
        final=torch.load(folder/'final.pt',weights_only=False);assert final['rng']==rng.bit_generator.state
        for state in final['optimizer']['state'].values():assert int(state['step'])==updates and all(torch.isfinite(v).all() for v in state.values() if torch.is_tensor(v))
        assert all(torch.isfinite(v).all() for v in final['model'].values());accounting[name]=dict(updates=updates,presentations=len(indices)*len(trace))
        print('Verified objective',name,flush=True)
    cs=[dict(epoch=e,mse=sum(s for s,n in v)/sum(n for s,n in v)) for e,v in scores.items()];selection=fit.read(fit.REPORT/'selection.json')
    assert cs==selection['candidates'] and selection['selected']==min(cs,key=lambda c:(c['mse'],c['epoch']))
    selected=torch.load(fit.WORK/'selected.pt',weights_only=True);final=torch.load(fit.WORK/'refit/final.pt',weights_only=False)['model'];assert all(torch.equal(v,final[k]) for k,v in selected.items())
    actual=assessment.evaluate();assert actual==fit.read(fit.WORK/'predictions.json');result=fit.read(fit.REPORT/'result.json')
    assert actual['summary']==result['summary'] and actual['checks']==result['checks'] and actual['all_checks_pass']==result['all_checks_pass']
    windows,maps=fit.base.heading.original.load();_,history,_=fit.base.prior.encoded(windows,maps,architecture)
    predictor=ObjectivePredictor();turns=0;records={(r['key'],r['position']):r for r in actual['records']}
    for w in [w for w in windows if w['partition']=='evaluation'][:2]:
        state=None
        for i,s in enumerate(w['steps']):
            v=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state,previous_moves=history[w['key']][i]);state=v['state'];turns+=1
            if not s['observed']:continue
            r=records[(w['key'],i)];assert r['selected']==state['objective_identity'] and r['reason']==v['objective_decision']
            torch.testing.assert_close(torch.tensor(v['objective_scores']),torch.tensor(r['scores']),atol=2e-6,rtol=2e-5)
            own=s['input']['observation']['own'].get('position')
            if own is not None:
                from .model import OFFSETS
                dx,dy=OFFSETS[r['adaptive']];assert v['objective_movement']==(own['x']+dx,own['y']+dy)
    immutable_json(fit.REPORT/'verification.json',dict(source_sha256=digest(__file__),result_sha256=digest(fit.REPORT/'result.json'),labels_exact=len(y),feature_banks_exact=5,
        validation_measurements=16,accounting=accounting,all_forecasts_exact=True,streaming_turns=turns,seconds=time.perf_counter()-start))
    print('VERIFIED objective selection and termination',flush=True)


if __name__=='__main__':run()
