"""Direct input, optimizer, weight, forecast and streaming verification."""
import argparse,time
import numpy as np
import torch
from . import shared_goal_execution_fit as fit
from .planner_weight_verify import equal
from .shared_goal_execution_predictor import SharedExecutionPlanner
from ..audit import immutable_json
from ..data import digest


def prefit():
    p,_,_,cache,ids=fit.inputs();fit.check(fit.read(fit.REPORT/'cache.json'));torch.set_num_threads(1);rows=fit.previous.records(fit.prior.base.dataset('full',cache),ids);counts={}
    for name in ['fold0','fold1','fold2','fold3','full']:
        bank=torch.load(fit.WORK/(name+'.pt'),weights_only=False);old=torch.load(fit.previous.WORK/(name+'.pt'),weights_only=True);rs=bank['records']
        assert [{k:r[k] for k in original} for r,original in zip(rs,rows)]==rows and len(rs)==12318
        assert all(torch.equal(bank[k],old[k]) for k in ('context','baseline','support','labels'))
        active=torch.tensor([r['active'] for r in rs]);assert torch.equal(bank['goal'][...,7],active[:,None].expand(-1,9).float());assert (bank['goal'][~active]==0).all();assert torch.isfinite(bank['goal']).all()
        assert torch.equal(bank['goal'][:,0,8],torch.tensor([r['utility'] for r in rs]));assert (bank['goal'][active,:,8]>0).all() and (bank['goal'][active,:,8]<=1).all()
        indices=torch.cat((active.nonzero().flatten()[:64],(~active).nonzero().flatten()[:64]));a=fit.new('blind',p);b=fit.new('goal',p);assert equal(a.state_dict(),b.state_dict())
        for net in (a,b):
            pred=net(bank['context'][indices],bank['goal'][indices],bank['baseline'][indices]);assert torch.equal(pred,bank['baseline'][indices]);loss=torch.nn.functional.cross_entropy(pred.masked_fill(~bank['support'][indices],-1e9),bank['labels'][indices]);loss.backward();assert all(v.grad is None or torch.isfinite(v.grad).all() for v in net.parameters());assert net.layers[-1].weight.grad.abs().sum()>0
        counts[name]=dict(rows=len(rs),active=int(active.sum()))
    immutable_json(fit.REPORT/'prefit-verification.json',dict(plan_sha256=digest(fit.REPORT/'plan.json'),cache_sha256=digest(fit.REPORT/'cache.json'),source_sha256=digest(__file__),counts=counts,matched_initializations=5,baseline_initial_exact=True,finite_backward_both_strata=True,optimizer_updates=0));print('VERIFIED shared executor prefit',flush=True)


def audit_run(directory,arm,bank,indices,p,epochs,held=None):
    net=fit.new(arm,p);initial=torch.load(directory/'epoch-000.pt',weights_only=True);assert equal(initial,net.state_dict());trace=fit.read(directory/'trace.json');rng=np.random.default_rng(p['seed']);updates=0;values={}
    assert len(trace['epochs'])==epochs
    for e in trace['epochs']:
        assert e['order']==rng.permutation(indices).tolist();assert len(e['norms'])==(len(indices)+p['batch']-1)//p['batch'] and np.isfinite(e['norms']).all() and np.isfinite(e['online_nll']);updates+=len(e['norms'])
    final=torch.load(directory/'final.pt',weights_only=False);assert final['rng']==rng.bit_generator.state
    for group in final['optimizer']['param_groups']:
        assert group['lr']==p['lr'] and group['weight_decay']==p['weight_decay']
    for state in final['optimizer']['state'].values():assert int(state['step'])==updates and all(not torch.is_tensor(v) or torch.isfinite(v).all() for v in state.values())
    assert all(torch.isfinite(v).all() for v in final['model'].values())
    if epochs:assert not equal(initial,final['model'])
    if held is not None:
        for epoch in range(0,epochs+1,p['every']):
            net.load_state_dict(torch.load(directory/f'epoch-{epoch:03d}.pt',weights_only=True));values[epoch]=fit.score(net,bank,held);assert equal(values[epoch],trace['validation'][str(epoch)])
    return values,updates,final


def run():
    start=time.perf_counter();p,parent,architecture,cache,ids=fit.inputs();torch.set_num_threads(1)
    for name in ('cache','fit','result','weight-inspection'):fit.check(fit.read(fit.REPORT/(name+'.json')))
    proof=fit.read(fit.REPORT/'prefit-verification.json');assert proof['plan_sha256']==digest(fit.REPORT/'plan.json') and proof['cache_sha256']==digest(fit.REPORT/'cache.json')
    selection=fit.read(fit.REPORT/'selection.json');updates=0;final_changes={}
    for arm in fit.ARMS:
        values={}
        for fold in range(4):
            name=f'fold{fold}';bank=torch.load(fit.WORK/(name+'.pt'),weights_only=False);rs=bank['records'];ix=np.array([i for i,r in enumerate(rs) if r['fold']!=fold]);held=np.array([i for i,r in enumerate(rs) if r['fold']==fold and r['canonical']]);v,u,final=audit_run(fit.WORK/arm/name,arm,bank,ix,p,p['epochs'],held);updates+=u
            for e,s in v.items():values.setdefault(e,[]).append(s)
            a=fit.read(fit.WORK/'blind'/name/'trace.json');b=fit.read(fit.WORK/'goal'/name/'trace.json');assert [e['order'] for e in a['epochs']]==[e['order'] for e in b['epochs']]
            initial=fit.new(arm,p).state_dict();final_changes[arm+'/'+name]={k:float((v-initial[k]).norm()) for k,v in final['model'].items()}
        cs=[dict(epoch=e,**{k:sum(v[k] for v in vs) for k in ('rows','correct','nll_sum')}) for e,vs in values.items()];assert cs==selection['candidates'][arm] and fit.previous.select(cs)==selection['selected'][arm]
        bank=torch.load(fit.WORK/'full.pt',weights_only=False);_,u,final=audit_run(fit.WORK/arm/'refit',arm,bank,np.arange(len(bank['records'])),p,selection['selected'][arm]['epoch']);updates+=u;assert equal(final['model'],torch.load(fit.WORK/(arm+'-selected.pt'),weights_only=True))
    torch.set_num_threads(4);windows,maps=fit.prior.base.heading.original.load();result=fit.read(fit.REPORT/'result.json');actual=fit.assessment();assert all(equal(v,result[k]) for k,v in actual.items())
    for split in ('fit','evaluation'):
        bank=torch.load(fit.WORK/(split+'.pt'),weights_only=False);old=torch.load(fit.calibration.WORK/(split+'.pt'),weights_only=False);assert all(torch.equal(bank[k],old[k]) for k in ('context','baseline','support'));assert equal(bank['records'],old['records'])
        lookup={(r['key'],r['position']):bank['context'][i] for i,r in enumerate(bank['records'])};gs=fit.goals([w for w in windows if w['partition']==split],maps,lookup,'full');assert torch.equal(torch.stack([gs[(r['key'],r['position'])]['goal'] for r in bank['records']]),bank['goal'])
        original=fit.read(fit.calibration.REPORT/'result.json')['results'][split]['direct'];assert result['results'][split]['direct']['predictions']==original['predictions'] and result['results'][split]['direct']['losses']==original['losses']
    # Independently replay selected raw fitting windows to check goal/cache construction.
    expanded,expanded_maps=fit.prior.base.heading.expanded.read();probe_max_error=dict(context=0.,baseline=0.,goal=0.)
    for fold in range(4):
        name=f'fold{fold}';bank=torch.load(fit.WORK/(name+'.pt'),weights_only=False);chosen=[]
        for active in (True,False):
            keys={r['key'] for r in bank['records'] if r['fold']!=fold and r['active']==active}
            for w in expanded:
                if w['key'] in keys and w not in chosen:chosen.append(w);break
        actual=fit.calibration.build(chosen,expanded_maps,name,parent,architecture);lookup={(r['key'],r['position']):actual['context'][i] for i,r in enumerate(actual['records'])};gs=fit.goals(chosen,expanded_maps,lookup,name);old={(r['key'],r['position']):i for i,r in enumerate(bank['records'])}
        for j,r in enumerate(actual['records']):
            key=(r['key'],r['position'])
            if key not in old:continue
            i=old[key]
            # Batched and single-window linear algebra can round differently.
            for field,tolerance in [('context',1e-6),('baseline',5e-6),('goal',1e-7)]:
                value=gs[key]['goal'] if field=='goal' else actual[field][j];error=float((bank[field][i]-value).abs().max());probe_max_error[field]=max(probe_max_error[field],error);assert error<=tolerance
            assert torch.equal(bank['context'][i,56:],actual['context'][j,56:]) and torch.equal(bank['goal'][i,:,:8],gs[key]['goal'][:,:8]);assert bank['records'][i]['selected']==gs[key]['selected']
            for arm in fit.ARMS:
                net=fit.new(arm,p);epoch=selection['selected'][arm]['epoch'];net.load_state_dict(torch.load(fit.WORK/arm/name/f'epoch-{epoch:03d}.pt',weights_only=True))
                with torch.no_grad():
                    cached=net(bank['context'][i],bank['goal'][i],bank['baseline'][i]).masked_fill(~bank['support'][i],-1e9).log_softmax(-1)
                    raw=net(actual['context'][j],gs[key]['goal'],actual['baseline'][j]).masked_fill(~actual['support'][j],-1e9).log_softmax(-1)
                assert cached.argmax()==raw.argmax() and float((cached[bank['support'][i]]-raw[bank['support'][i]]).abs().max())<1e-5
    _,history,_=fit.prior.base.prior.encoded(windows,maps,architecture);bank=torch.load(fit.WORK/'evaluation.pt',weights_only=False);evaluation=[w for w in windows if w['partition']=='evaluation'];activity={w['key']:sum(r['active'] for r in bank['records'] if r['key']==w['key']) for w in evaluation};chosen=[evaluation[0]]
    for w in sorted(evaluation,key=lambda w:-activity[w['key']]):
        if w not in chosen:chosen.append(w)
        if len(chosen)==3:break
    turns=active=without=0
    for arm in fit.ARMS:
        predictor=SharedExecutionPlanner(arm);expected={(r['key'],r['position']):(r,pred) for r,pred in zip(bank['records'],result['results']['evaluation'][arm]['predictions'])}
        for w in chosen:
            state=None
            for i,s in enumerate(w['steps']):
                value=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state,previous_moves=history[w['key']][i]);state=value['state'];turns+=1
                if not s['observed']:continue
                r,pred=expected[(w['key'],i)];assert state['objective_identity']==r['selected'];own=s['input']['observation']['own'].get('position')
                if own is not None:
                    dx,dy=fit.prior.model.OFFSETS[pred];assert value['shared_movement']==(own['x']+dx,own['y']+dy) and value['shared_execution_used'];active+=r['active'];without+=not r['active']
    assert active>0 and without>0
    immutable_json(fit.REPORT/'verification.json',dict(result_sha256=digest(fit.REPORT/'result.json'),source_sha256=digest(__file__),fold_measurements=40,optimizer_updates_accounted=updates,matched_sampling=True,selected_weights_exact=True,all_summaries_reproduced=True,goal_inputs_reconstructed=True,raw_fitting_window_probes=8,raw_probe_max_abs_error=probe_max_error,raw_probe_predictions_exact=True,streaming_turns=turns,active_streaming_queries=active,absent_goal_streaming_queries=without,final_fold_weight_change_norms=final_changes,optimizer_replays=0,seconds=time.perf_counter()-start));print('VERIFIED shared executor',updates,turns,active,without,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('prefit','run'));globals()[parser.parse_args().command]()
