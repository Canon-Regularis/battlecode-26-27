"""Reproduce direct weight arithmetic, fold selection and actual streaming policy."""
import time
import torch
from . import planner_weight_edit as fit
from .planner_weight_predictor import EditedPlannerPredictor
from ..audit import immutable_json
from ..data import digest


def equal(a,b):
    if torch.is_tensor(a):return torch.equal(a,b)
    if isinstance(a,dict):return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    if isinstance(a,list):return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a==b


def run():
    start=time.perf_counter();p,parent,architecture,_,ids=fit.inputs();torch.set_num_threads(4)
    selection=fit.read(fit.REPORT/'selection.json');result=fit.read(fit.REPORT/'result.json');fit.check(selection);fit.check(result)
    windows,maps=fit.old.base.heading.expanded.read();assert all(w['key']==ids[i]['key'] and w['partition']=='fit' for i,w in enumerate(windows))
    targets={(r['key'],r['position']):r for r in fit.read(fit.old.WORK/'rows.json')};banks=[]
    for fold in range(4):
        ws=[w for i,w in enumerate(windows) if ids[i]['canonical'] and ids[i]['fold']==fold]
        actual=fit.build(ws,maps,'fold'+str(fold),parent,architecture,targets);saved=torch.load(fit.WORK/f'fold{fold}.pt',weights_only=False);assert equal(actual,saved);banks.append(saved)
        print('Verified weight-edit fold',fold,flush=True)
    cs=[dict(scale=scale,shift=shift,**fit.combined([fit.simulate(b,scale,shift) for b in banks])) for scale in p['scales'] for shift in p['shifts']]
    assert cs==selection['candidates'];chosen=fit.choose_edit(cs,p);assert chosen==selection['selected']
    assert fit.combined([fit.simulate(b,disabled=True) for b in banks])==selection['disabled_control']
    original=torch.load(fit.old.WORK/'selected.pt',weights_only=True);edited=torch.load(fit.WORK/'selected.pt',weights_only=True)
    expected=fit.edit(original,chosen['scale'],chosen['shift']);assert equal(edited,expected)
    changed=[k for k,v in original.items() if not torch.equal(v,edited[k])];assert all(k.startswith('net.2.') for k in changed)
    windows,maps=fit.old.base.heading.original.load();_,history,_=fit.old.base.prior.encoded(windows,maps,architecture)
    examples=fit.old.examples(windows,maps,history,[dict(fold=-1,canonical=True) for w in windows]);targets={(r['key'],r['position']):r for r in examples};exact={}
    for split in ('fit','evaluation'):
        actual=fit.build([w for w in windows if w['partition']==split],maps,'full',parent,architecture,targets);saved=torch.load(fit.WORK/(split+'.pt'),weights_only=False);assert equal(actual,saved)
        scores=dict(edited=fit.simulate(saved,chosen['scale'],chosen['shift']),original=fit.simulate(saved),disabled=fit.simulate(saved,disabled=True))
        assert scores==result['results'][split];old=fit.read(fit.old.REPORT/'result.json')['summary'][split]
        assert scores['original']['correct']==old['adaptive'] and scores['original']['baseline']==old['baseline']
        assert scores['disabled']['correct']==scores['disabled']['baseline'] and scores['disabled']['active']==0
        exact[split]=len(saved['records'])
    x=result['results']['evaluation']['edited'];b=result['results']['evaluation']['original'];gates=dict(combined_gain=x['correct']>b['correct'],direct_gain=x['correct']>x['baseline'],utility=x['utility_sum']>0,active=x['active']>=.1*x['available'])
    assert result['checks']==gates and result['all_checks_pass']==all(gates.values())
    bank=torch.load(fit.WORK/'evaluation.pt',weights_only=False);scores=result['results']['evaluation']['edited'];expected={(r['key'],r['position']):(pr,key) for r,pr,key in zip(bank['records'],scores['predictions'],scores['selected'])}
    predictor=EditedPlannerPredictor();turns=0
    for w in [w for w in windows if w['partition']=='evaluation'][:2]:
        state=None
        for i,s in enumerate(w['steps']):
            value=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state,previous_moves=history[w['key']][i]);state=value['state'];turns+=1
            if not s['observed']:continue
            pred,key=expected[(w['key'],i)];assert key==state['objective_identity'];own=s['input']['observation']['own'].get('position')
            if own is not None:
                dx,dy=fit.model.OFFSETS[pred];assert value['objective_movement']==(own['x']+dx,own['y']+dy)
    immutable_json(fit.REPORT/'verification.json',dict(result_sha256=digest(fit.REPORT/'result.json'),source_sha256=digest(__file__),changed_tensors=changed,exact_forecasts=exact,fold_caches_exact=4,
        edit_candidates_exact=len(cs),disabled_control_exact=True,streaming_turns=turns,optimizer_updates=0,seconds=time.perf_counter()-start))
    print('VERIFIED planner weight edits',changed,flush=True)


if __name__=='__main__':run()
