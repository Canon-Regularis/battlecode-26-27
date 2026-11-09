"""Verify bounded readout training and causal runtime without optimizer replay."""
import time
import numpy as np
import torch
from . import planner_margin_fit as fit
from . import planner_readout_fit as common
from .planner_weight_verify import equal
from .planner_margin_predictor import MarginPlanner
from ..audit import immutable_json
from ..data import digest


def run():
    start=time.perf_counter();p=fit.inputs();_,_,architecture,_,ids=common.inputs();torch.set_num_threads(4)
    for name in ('fit','result'):fit.check(fit.read(fit.REPORT/(name+'.json')))
    selection=fit.read(fit.REPORT/'selection.json');values={};updates=0;groups={r['key']:r['fold'] for r in ids}
    for fold in range(4):
        bank=torch.load(common.WORK/f'fold{fold}.pt',weights_only=False);directory=fit.WORK/f'fold{fold}'
        assert all(r['split']=='fit' and groups[r['key']]==r['fold'] for r in bank['records'])
        held=[dict(r) for r in bank['records'] if r['fold']==fold]
        for r in held:r.pop('fold')
        old=torch.load(common.prior.WORK/f'fold{fold}.pt',weights_only=False)
        assert equal(held,old['records'])
        net=common.Readout(bank['weights']);assert equal(net.state_dict(),torch.load(directory/'epoch-000.pt',weights_only=True))
        indices=np.array([i for i,r in enumerate(bank['records']) if r['fold']!=fold and (r['label']>=0 or r['utilities'] is not None)])
        trace=fit.read(directory/'trace.json');rng=np.random.default_rng(p['seed'])
        for e in trace['epochs']:
            assert e['order']==rng.permutation(indices).tolist()
            assert len(e['norms'])==(len(indices)+p['batch']-1)//p['batch'] and np.isfinite(e['norms']).all()
            updates+=len(e['norms'])
        final=torch.load(directory/'final.pt',weights_only=False)
        assert final['rng']==rng.bit_generator.state
        expected=p['epochs']*((len(indices)+p['batch']-1)//p['batch'])
        assert all(int(s['step'])==expected for s in final['optimizer']['state'].values())
        assert all(not torch.equal(v,net.state_dict()[k]) for k,v in final['model'].items())
        for epoch in range(0,p['epochs']+1,4):
            net.load_state_dict(torch.load(directory/f'epoch-{epoch:03d}.pt',weights_only=True));value=common.score(net,bank,fold)
            assert value==trace['validation'][str(epoch)];values.setdefault(epoch,[]).append(value)
    candidates=[dict(epoch=e,**common.prior.combined(v)) for e,v in values.items()]
    assert candidates==selection['candidates'] and common.choose(candidates,p)==selection['selected']
    bank=torch.load(common.WORK/'full.pt',weights_only=False);net=common.Readout(bank['weights']);final=torch.load(fit.WORK/'refit/final.pt',weights_only=False);net.load_state_dict(final['model'])
    selected=torch.load(fit.WORK/'selected.pt',weights_only=True);assert equal(selected,common.export(net,bank['weights']))
    if selection['selected']['epoch']==0:
        assert equal(selected,bank['weights']) and not final['optimizer']['state']
    result=fit.read(fit.REPORT/'result.json');exact={}
    for split in ('fit','evaluation'):
        bank=torch.load(common.prior.WORK/(split+'.pt'),weights_only=False)
        assert all(torch.equal(selected[k],bank['weights'][k]) for k in ('net.0.weight','net.0.bias'))
        actual=common.prior.simulate(dict(bank,weights=selected));assert actual==result['results'][split];exact[split]=len(bank['records'])
    x=result['results']['evaluation'];b=fit.read(common.prior.REPORT/'result.json')['results']['evaluation']['edited']
    gates=dict(combined=x['correct']>b['correct'],direct=x['correct']>x['baseline'],utility=x['utility_sum']>0,active=x['active']>=.1*x['available'])
    assert gates==result['checks'] and all(gates.values())==result['all_checks_pass'] and (x['correct']/x['rows']>=.8)==result['target_met']
    windows,maps=common.prior.old.base.heading.original.load();_,history,_=common.prior.old.base.prior.encoded(windows,maps,architecture)
    bank=torch.load(common.prior.WORK/'evaluation.pt',weights_only=False);expected={(r['key'],r['position']):(a,b) for r,a,b in zip(bank['records'],x['predictions'],x['selected'])}
    predictor=MarginPlanner();turns=0
    for w in [w for w in windows if w['partition']=='evaluation'][:2]:
        state=None
        for i,s in enumerate(w['steps']):
            value=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state,previous_moves=history[w['key']][i]);state=value['state'];turns+=1
            if not s['observed']:continue
            pred,key=expected[(w['key'],i)];assert key==state['objective_identity'];own=s['input']['observation']['own'].get('position')
            if own is not None:
                dx,dy=common.prior.model.OFFSETS[pred];assert value['objective_movement']==(own['x']+dx,own['y']+dy)
    immutable_json(fit.REPORT/'verification.json',dict(result_sha256=digest(fit.REPORT/'result.json'),source_sha256=digest(__file__),fold_measurements=20,training_updates_checked=updates,exact_forecasts=exact,streaming_turns=turns,selected_epoch=selection['selected']['epoch'],optimizer_replays=0,seconds=time.perf_counter()-start))
    print('VERIFIED margin readout selection and runtime',flush=True)


if __name__=='__main__':run()
