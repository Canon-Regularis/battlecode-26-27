"""Reproduce waypoint labels, feature banks, selection and deployment-facing outputs."""
import time
from pathlib import Path
import numpy as np
import torch
from . import strategic_waypoint_fit as fit
from .strategic_waypoint import labels,commitment
from .strategic_waypoint_predictor import StrategicWaypointPredictor
from ..audit import immutable_json
from ..data import digest


def run():
    start=time.perf_counter();plan,parent,architecture,cache,ids=fit.inputs();fit.check(fit.read(fit.REPORT/'fit.json'));fit.check(fit.read(fit.REPORT/'result.json'))
    torch.set_num_threads(1);windows,maps=fit.base.heading.expanded.read();history,bound=fit.audit.prior_moves(windows);rows=[]
    assert bound==fit.read(fit.REPORT/'cache.json')['source_bindings']
    for wi,w in enumerate(windows):
        for r in labels(w,history[w['key']],8):rows.append(dict(r,window=wi,**ids[wi],payload=w['payload']))
    assert rows==fit.read(fit.WORK/'rows.json');values={};accounting={}
    for name in ['fold0','fold1','fold2','fold3','full']:
        all_x=fit.cached_features(name,parent,architecture,cache);x=torch.stack([all_x[r['window'],r['position']] for r in rows])
        assert torch.equal(x,torch.load(fit.WORK/(name+'.pt'),weights_only=True))
        folder=fit.WORK/name if name!='full' else fit.WORK/'refit';trace=fit.read(folder/'trace.json');net=fit.new(plan)
        assert all(torch.equal(v,torch.load(folder/'epoch-000.pt',weights_only=True)[k]) for k,v in net.state_dict().items())
        if name!='full':
            fold=int(name[-1]);indices=np.array([i for i,r in enumerate(rows) if r['fold']!=fold]);held=np.array([i for i,r in enumerate(rows) if r['fold']==fold and r['canonical']])
        else:indices=np.arange(len(rows));held=None
        rng=np.random.default_rng(plan['seed']);updates=0
        for e in trace['epochs']:
            assert e['order']==rng.permutation(indices).tolist() and np.isfinite(e['gradient_norms']).all()
            assert len(e['gradient_norms'])==(len(indices)+plan['batch_rows']-1)//plan['batch_rows'];updates+=len(e['gradient_norms'])
        final=torch.load(folder/'final.pt',weights_only=False);assert final['rng']==rng.bit_generator.state
        for state in final['optimizer']['state'].values():assert int(state['step'])==updates and all(torch.isfinite(v).all() for v in state.values() if torch.is_tensor(v))
        for epoch,saved_score in trace['validation'].items():
            net.load_state_dict(torch.load(folder/f'epoch-{int(epoch):03d}.pt',weights_only=True));actual=fit.score(net,x,rows,held,maps);assert actual==saved_score
            values.setdefault(int(epoch),[]).append(actual)
        accounting[name]=dict(updates=updates,presentations=len(indices)*len(trace['epochs']))
        print('Verified waypoint',name,flush=True)
    candidates=[dict(epoch=e,rows=sum(s['rows'] for s in v),error_sum=sum(s['error_sum'] for s in v),within2=sum(s['within2'] for s in v)) for e,v in values.items()]
    selection=fit.read(fit.REPORT/'selection.json');assert candidates==selection['candidates']
    assert selection['selected']==min(candidates,key=lambda s:(s['error_sum']/s['rows'],-s['within2'],s['epoch']))
    selected=torch.load(fit.WORK/'selected.pt',weights_only=False)['model'];final=torch.load(fit.WORK/'refit/final.pt',weights_only=False)['model']
    assert all(torch.equal(v,final[k]) for k,v in selected.items())
    actual=fit.evaluate();assert actual==fit.read(fit.WORK/'predictions.json');result=fit.read(fit.REPORT/'result.json')
    assert actual['summary']==result['summary'] and actual['checks']==result['checks'] and actual['all_checks_pass']==result['all_checks_pass']
    windows,maps=fit.base.heading.original.load();_,history,_=fit.base.prior.encoded(windows,maps,architecture)
    predictor=StrategicWaypointPredictor();w=next(w for w in windows if w['partition']=='evaluation');state=None;turns=0
    from .strategic_waypoint import reachable_goal,position
    records={(r['key'],r['position']):r for r in actual['moves']}
    for i,s in enumerate(w['steps']):
        value=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state,previous_moves=history[w['key']][i]);state=value['state'];turns+=1
        origin=position(s)
        if origin is not None:
            assert value['strategic_waypoint']==reachable_goal(origin,actual['offsets'][w['key']][i],maps[w['payload']])
            if s['movement'] is not None:
                gold=tuple(origin[j]+s['movement'][j] for j in (0,1));record=records[(w['key'],i)]
                assert (value['goal_guided_movement']==gold)==record['routed'] and (value['committed_movement']==gold)==record['committed']
    state=None
    for i in range(8):goal,state=commitment((0,0),(i+2,0),state);assert goal==(2,0)
    goal,state=commitment((0,0),(20,0),state);assert goal==(20,0)
    assert commitment(None,None,state)==(None,None)
    immutable_json(fit.REPORT/'verification.json',dict(result_sha256=digest(fit.REPORT/'result.json'),source_sha256=digest(__file__),
        labels_exact=len(rows),feature_banks_exact=5,validation_measurements=20,accounting=accounting,
        all_saved_forecasts_exact=True,streaming_turns=turns,commitment_tests_passed=True,seconds=time.perf_counter()-start))
    print('VERIFIED waypoint experiment',flush=True)


if __name__=='__main__':run()
